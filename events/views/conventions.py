import icalendar
import geopy.geocoders
import pytz
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from timezonefinder import TimezoneFinder

from ..auth import can_manage_events, organizer_required
from ..concat import attach_host_avatar_urls
from ..forms import ConventionForm
from ..models import Convention, PanelHost, Room, Tag
from ..rsvp import (
    filter_panels_for_user_rsvp,
    get_rsvp_user_id,
    get_user_rsvp_panel_ids,
    make_rsvp_feed_token,
)
from .schedule_grid import build_display_days, build_schedule_grid_payload, collect_panel_hosts


def convention_detail(request, pk):
    convention = get_object_or_404(Convention, pk=pk)
    days = convention.days.all().order_by('date')

    unique_tags = Tag.objects.filter(panels__convention_day__convention=convention).distinct().order_by('name')
    unique_rooms = Room.objects.filter(convention=convention).order_by('name')
    convention_hosts = (
        PanelHost.objects.filter(panels__convention_day__convention=convention)
        .distinct()
        .annotate(
            convention_panel_count=Count(
                'panels',
                filter=Q(panels__convention_day__convention=convention),
                distinct=True,
            )
        )
        .order_by('name')
    )

    display_days_with_panels = build_display_days(days)
    attach_host_avatar_urls(collect_panel_hosts(display_days_with_panels))
    attach_host_avatar_urls(convention_hosts)

    rsvp_user_id = get_rsvp_user_id(request)
    user_rsvp_panel_ids = get_user_rsvp_panel_ids(request, convention) if rsvp_user_id else set()
    rsvp_feed_token = make_rsvp_feed_token(rsvp_user_id) if rsvp_user_id else ''
    schedule_grid_payload = build_schedule_grid_payload(
        display_days_with_panels,
        user_rsvp_panel_ids,
    )

    return render(request, 'events/convention_detail.html', {
        'convention': convention,
        'days': display_days_with_panels,
        'schedule_grid_payload': schedule_grid_payload,
        'unique_tags': unique_tags,
        'unique_rooms': unique_rooms,
        'convention_hosts': convention_hosts,
        'current_convention_name': convention.name,
        'is_staff': can_manage_events(request),
        'can_manage_events': can_manage_events(request),
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


def convention_ical_feed(request, pk):
    convention = get_object_or_404(Convention, pk=pk)
    days = convention.days.all().order_by('date')
    rsvp_param = request.GET.get('rsvp')

    cal = icalendar.Calendar()
    cal.add('prodid', '-//FurConnect//Convention Schedule//EN')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', convention.name)

    tz_name = 'UTC'
    try:
        geolocator = geopy.geocoders.Nominatim(user_agent="furconnect-ical")
        location = geolocator.geocode(convention.location)
        if location:
            tf = TimezoneFinder()
            tz_name = tf.timezone_at(lng=location.longitude, lat=location.latitude) or 'UTC'
    except Exception:
        tz_name = 'UTC'

    cal.add('X-WR-TIMEZONE', tz_name)
    tz = pytz.timezone(tz_name)

    for day in days:
        panels = day.panels.filter(cancelled=False).order_by('start_time')
        if rsvp_param:
            panels = filter_panels_for_user_rsvp(panels, request, rsvp_param).order_by('start_time')
        for panel in panels:
            event = icalendar.Event()
            event.add('summary', panel.title or 'Untitled Event')
            event.add('description', panel.description or '')
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

            event.add('dtstart', start_datetime)
            event.add('dtend', end_datetime)
            event.add('dtstamp', timezone.now().astimezone(tz))
            event.add('uid', f'panel-{panel.pk}@furconnect')
            cal.add_component(event)

    response = HttpResponse(cal.to_ical(), content_type='text/calendar')
    response['Content-Disposition'] = f'inline; filename="{convention.name}_schedule.ics"'
    return response
