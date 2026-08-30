import icalendar
import geopy.geocoders
import hashlib
import pytz
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from timezonefinder import TimezoneFinder

from ..auth import can_manage_events, organizer_required
from ..catalog import build_public_host_catalog, speakers_from_catalog
from ..forms import ConventionForm
from ..models import Convention, Panel, PanelHost, Tag
from ..rsvp import (
    filter_panels_for_user_rsvp,
    get_rsvp_user_id,
    get_user_rsvp_panel_ids,
    make_rsvp_feed_token,
)
from .schedule_grid import build_display_days, build_schedule_grid_payload


def _convention_days_queryset(convention):
    return convention.days.prefetch_related(
        Prefetch(
            'panels',
            queryset=(
                Panel.objects.select_related('room', 'convention_day')
                .prefetch_related(
                    Prefetch(
                        'host',
                        queryset=PanelHost.objects.order_by('panelhostorder__priority'),
                        to_attr='ordered_hosts',
                    ),
                    Prefetch(
                        'tags',
                        queryset=Tag.objects.order_by('paneltag__priority'),
                        to_attr='ordered_tags',
                    ),
                )
                .order_by('start_time')
            ),
        ),
    ).order_by('date')


def convention_detail(request, pk):
    convention = get_object_or_404(Convention, pk=pk)
    days = _convention_days_queryset(convention)

    display_days_with_panels = build_display_days(days)
    host_catalog = build_public_host_catalog(convention)

    rsvp_user_id = get_rsvp_user_id(request)
    user_rsvp_panel_ids = get_user_rsvp_panel_ids(request, convention) if rsvp_user_id else set()
    rsvp_feed_token = make_rsvp_feed_token(rsvp_user_id) if rsvp_user_id else ''
    schedule_grid_payload = build_schedule_grid_payload(
        display_days_with_panels,
        user_rsvp_panel_ids,
    )
    can_manage = can_manage_events(request)

    return render(request, 'events/convention_detail.html', {
        'convention': convention,
        'days': display_days_with_panels,
        'schedule_grid_payload': schedule_grid_payload,
        'host_catalog': host_catalog,
        'unique_tags': host_catalog.get('tags') or [],
        'unique_rooms': host_catalog.get('rooms') or [],
        'convention_hosts': speakers_from_catalog(host_catalog),
        'current_convention_name': convention.name,
        'is_staff': can_manage,
        'can_manage_events': can_manage,
        'concat_enabled': settings.CONCAT_ENABLED,
        'concat_authenticated': bool(request.session.get('concat_user_id')),
        'concat_user_name': request.session.get('concat_user_name', ''),
        'user_rsvp_panel_ids': user_rsvp_panel_ids,
        'rsvp_feed_token': rsvp_feed_token,
    })


@organizer_required
def convention_create(request):
    if request.method == 'POST':
        form = ConventionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Convention created successfully!')
            return redirect('events:schedule')
    else:
        form = ConventionForm()

    current_convention = Convention.objects.first()
    current_convention_name = current_convention.name if current_convention else 'FurConnect'

    return render(request, 'events/convention_form.html', {
        'form': form,
        'action': 'Create',
        'current_convention_name': current_convention_name,
    })


@organizer_required
def convention_edit(request, pk):
    return redirect('events:admin_panel_section', pk=pk, section='settings')


@organizer_required
def convention_delete(request, pk):
    convention = get_object_or_404(Convention, pk=pk)
    if request.method == 'POST':
        convention.delete()
        messages.success(request, 'Convention deleted successfully!')
        return redirect('events:schedule')


def _timezone_name_for_location(location_name):
    location_name = (location_name or '').strip()
    cache_key = 'ical:tz:' + hashlib.md5(location_name.lower().encode('utf-8')).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    tz_name = 'UTC'
    if location_name:
        try:
            geolocator = geopy.geocoders.Nominatim(user_agent="furconnect-ical", timeout=2)
            location = geolocator.geocode(location_name)
            if location:
                tf = TimezoneFinder()
                tz_name = tf.timezone_at(lng=location.longitude, lat=location.latitude) or 'UTC'
        except Exception:
            tz_name = 'UTC'
    cache.set(cache_key, tz_name, 60 * 60 * 24 * 7)
    return tz_name


def _ical_calendar_name(convention, is_rsvp_feed):
    if is_rsvp_feed:
        return f'{convention.name} (My RSVPs)'
    return convention.name


def convention_ical_feed(request, pk, token=None):
    convention = get_object_or_404(Convention, pk=pk)
    days = convention.days.prefetch_related(
        Prefetch(
            'panels',
            queryset=Panel.objects.select_related('room').order_by('start_time'),
        ),
    ).order_by('date')
    rsvp_param = token or request.GET.get('rsvp')
    is_rsvp_feed = bool(rsvp_param)
    calendar_name = _ical_calendar_name(convention, is_rsvp_feed)

    cal = icalendar.Calendar()
    cal.add('prodid', '-//FurConnect//Convention Schedule//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('name', calendar_name)
    cal.add('X-WR-CALNAME', calendar_name)
    cal.add(
        'X-WR-CALDESC',
        f'Panels you RSVPed to at {convention.name}'
        if is_rsvp_feed
        else f'Full schedule for {convention.name}',
    )

    tz_name = _timezone_name_for_location(convention.location)
    cal.add('X-WR-TIMEZONE', 'UTC')
    tz = pytz.timezone(tz_name)

    for day in days:
        panels = day.panels.all()
        if rsvp_param:
            panels = filter_panels_for_user_rsvp(panels, request, rsvp_param).order_by('start_time')
        for panel in panels:
            event = icalendar.Event()
            title = panel.title or 'Untitled Event'
            if panel.cancelled:
                title = f'Cancelled: {title}'
            if is_rsvp_feed:
                title = f'{title} (RSVP)'
            event.add('summary', title)
            description = panel.description or ''
            if panel.cancelled:
                description = 'This event has been cancelled.\n\n' + description
            event.add('description', description.strip())
            room_name = panel.room.name if panel.room else ''
            event.add('location', f'{convention.name} - {room_name}' if room_name else convention.name)

            start_datetime = datetime.combine(day.date, panel.start_time)
            end_datetime = datetime.combine(day.date, panel.end_time)
            if start_datetime.tzinfo is None:
                start_datetime = tz.localize(start_datetime)
            else:
                start_datetime = start_datetime.astimezone(tz)
            if end_datetime.tzinfo is None:
                end_datetime = tz.localize(end_datetime)
            else:
                end_datetime = end_datetime.astimezone(tz)
            if end_datetime < start_datetime:
                end_datetime += timedelta(days=1)

            # UTC "Z" times import reliably in Google Calendar; TZID without VTIMEZONE often fails.
            start_utc = start_datetime.astimezone(pytz.UTC)
            end_utc = end_datetime.astimezone(pytz.UTC)
            event.add('dtstart', start_utc)
            event.add('dtend', end_utc)
            event.add('dtstamp', timezone.now().astimezone(pytz.UTC))
            event.add('uid', f'panel-{panel.pk}@furconnect')
            if panel.cancelled:
                event.add('status', 'CANCELLED')
                event.add('transp', 'TRANSPARENT')
            else:
                event.add('status', 'CONFIRMED')
                event.add('transp', 'OPAQUE')
            cal.add_component(event)

    response = HttpResponse(cal.to_ical(), content_type='text/calendar; charset=utf-8')
    # No Content-Disposition: Google Calendar treats that as a file download, not a live feed.
    response['Cache-Control'] = 'public, max-age=300'
    return response
