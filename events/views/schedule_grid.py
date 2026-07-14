from datetime import datetime, time

from django.utils.text import slugify


def attach_panel_ordering(panel):
    panel.ordered_hosts = list(panel.host.all().order_by('panelhostorder__priority'))
    panel.ordered_tags = list(panel.tags.all().order_by('paneltag__priority'))


def build_display_days(days):
    """Group panels by day and start time for list view."""
    panels_by_display_time = {}

    for day in days:
        panels_by_display_time[day.date] = {}
        for panel in day.panels.all().order_by('start_time'):
            attach_panel_ordering(panel)
            start_time = panel.start_time
            panels_by_display_time[day.date].setdefault(start_time, []).append(panel)

    display_days_with_panels = []
    for day_date in sorted(panels_by_display_time.keys()):
        day_obj = days.get(date=day_date)
        display_day = {
            'original_day_obj': day_obj,
            'panels_by_time': [
                {
                    'start_time': slot_time,
                    'panels': panels_by_display_time[day_date][slot_time],
                }
                for slot_time in sorted(panels_by_display_time[day_date].keys())
            ],
        }
        display_days_with_panels.append(display_day)

    return display_days_with_panels


def collect_panel_hosts(display_days_with_panels):
    hosts = []
    for display_day in display_days_with_panels:
        for time_group in display_day['panels_by_time']:
            for panel in time_group['panels']:
                hosts.extend(panel.ordered_hosts)
    return hosts


def _panels_for_day(display_day):
    panels = []
    for time_group in display_day['panels_by_time']:
        panels.extend(time_group['panels'])
    return panels


def _rooms_for_panels(panels_for_day):
    rooms_used = []
    for panel in panels_for_day:
        if panel.room_id and panel.room and panel.room not in rooms_used:
            rooms_used.append(panel.room)

    def room_sort_key(room):
        room_panels = [panel for panel in panels_for_day if panel.room_id == room.id]
        first_start = min((panel.start_time for panel in room_panels), default=time.max)
        return (first_start, room.name or '')

    return sorted(
        (room for room in rooms_used if room and room.id),
        key=room_sort_key,
    )


def _panel_event_bounds(day_date, panel):
    start_dt = datetime.combine(day_date, panel.start_time)
    end_dt = datetime.combine(day_date, panel.end_time)
    if end_dt <= start_dt:
        end_dt = start_dt.replace(hour=23, minute=59, second=0, microsecond=0)
        if end_dt <= start_dt:
            end_dt = start_dt
    return start_dt, end_dt


def _contrast_text_for_accent(accent):
    """Pick dark or light text to match list-view panel cards."""
    color = (accent or '').lstrip('#')
    if len(color) != 6:
        return '#1a1d21'
    try:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
    except ValueError:
        return '#1a1d21'
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return '#1a1d21' if luminance > 0.5 else '#f8f9fa'


def _truncate_text(value, limit=120):
    text = ' '.join((value or '').split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + '…'


def _panel_to_fc_event(panel, day_date, user_rsvp_panel_ids):
    if not panel.room_id:
        return None

    start_dt, end_dt = _panel_event_bounds(day_date, panel)
    accent = '#ffc107'
    if panel.ordered_tags:
        accent = panel.ordered_tags[0].color or accent
    text_color = _contrast_text_for_accent(accent)

    tags = [tag.name.lower() for tag in panel.ordered_tags]
    room_name = panel.room.name if panel.room else ''
    room_slug = slugify(room_name) if room_name else ''

    def _fmt_time(value):
        try:
            return value.strftime('%-I:%M %p')
        except ValueError:
            return value.strftime('%I:%M %p').lstrip('0')

    time_label = f'{_fmt_time(panel.start_time)} - {_fmt_time(panel.end_time)}'

    hosts = []
    for host in panel.ordered_hosts[:4]:
        hosts.append({
            'id': host.id,
            'name': host.name,
            'avatarUrl': getattr(host, 'avatar_url', None) or host.get_profile_picture() or '',
        })

    return {
        'id': str(panel.pk),
        'resourceId': str(panel.room_id),
        'title': panel.title,
        'start': start_dt.isoformat(),
        'end': end_dt.isoformat(),
        'backgroundColor': accent,
        'borderColor': accent,
        'textColor': text_color,
        'extendedProps': {
            'accent': accent,
            'description': _truncate_text(panel.description, 220),
            'timeLabel': time_label,
            'roomName': room_name,
            'tags': tags,
            'tagColors': [tag.color for tag in panel.ordered_tags if tag.color][:4],
            'roomSlug': room_slug,
            'rsvped': panel.pk in user_rsvp_panel_ids,
            'cancelled': bool(panel.cancelled),
            'featured': bool(getattr(panel, 'is_featured', False)),
            'hosts': hosts,
            'searchText': ' '.join(
                [
                    panel.title or '',
                    panel.description or '',
                    ' '.join(tags),
                    ' '.join(host.name for host in panel.ordered_hosts),
                ]
            ).lower(),
        },
    }


def build_schedule_grid_payload(display_days_with_panels, user_rsvp_panel_ids=None):
    """JSON payload for FullCalendar resourceTimeGridDay (rooms as columns)."""
    user_rsvp_panel_ids = user_rsvp_panel_ids or set()
    days_payload = []

    for display_day in display_days_with_panels:
        day_obj = display_day['original_day_obj']
        if not day_obj:
            continue

        day_date = day_obj.date
        panels_for_day = _panels_for_day(display_day)
        rooms_used = _rooms_for_panels(panels_for_day)

        slot_min = None
        slot_max = None
        if panels_for_day:
            min_start = min(panel.start_time for panel in panels_for_day)
            max_end = max(panel.end_time for panel in panels_for_day)
            slot_min = min_start.replace(minute=0, second=0, microsecond=0).strftime('%H:%M:%S')
            end_hour = max_end.hour + (1 if max_end.minute or max_end.second else 0)
            if end_hour > 23:
                slot_max = '24:00:00'
            else:
                slot_max = f'{end_hour:02d}:00:00'

        events = []
        for panel in panels_for_day:
            event = _panel_to_fc_event(panel, day_date, user_rsvp_panel_ids)
            if event:
                events.append(event)

        days_payload.append({
            'dayId': day_obj.id,
            'date': day_date.isoformat(),
            'label': day_date.strftime('%A, %b %d, %Y'),
            'slotMinTime': slot_min or '08:00:00',
            'slotMaxTime': slot_max or '22:00:00',
            'resources': [
                {'id': str(room.id), 'title': room.name}
                for room in rooms_used
            ],
            'events': events,
        })

    return {'days': days_payload}
