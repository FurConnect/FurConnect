from datetime import datetime, timedelta, time
import math


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


def _round_grid_bounds(day_date, panels_for_day):
    if panels_for_day:
        min_start_time = min(panel.start_time for panel in panels_for_day)
        max_end_time = max(panel.end_time for panel in panels_for_day)

        start_dt = datetime.combine(day_date, min_start_time)
        if start_dt.minute < 30:
            start_dt = start_dt.replace(minute=0, second=0, microsecond=0)
        else:
            start_dt = start_dt.replace(minute=30, second=0, microsecond=0)

        end_dt = datetime.combine(day_date, max_end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        if not (end_dt.minute == 0 and end_dt.second == 0 and end_dt.microsecond == 0):
            if end_dt.minute <= 30:
                end_dt = end_dt.replace(minute=30, second=0, microsecond=0)
            else:
                end_dt = (end_dt + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        if end_dt <= start_dt + timedelta(hours=1):
            end_dt = start_dt + timedelta(hours=1)
        return start_dt, end_dt

    start_dt = datetime.combine(day_date, time(0, 0))
    end_dt = datetime.combine(day_date, time(23, 30)) + timedelta(minutes=30)
    return start_dt, end_dt


def _panel_slot_entry(panel, day_date, start_dt):
    room_id = panel.room_id
    if not room_id:
        return None

    panel_start = datetime.combine(day_date, panel.start_time)
    panel_end = datetime.combine(day_date, panel.end_time)
    if panel_end <= panel_start:
        panel_end += timedelta(days=1)

    start_minute = 0 if panel_start.minute < 30 else 30
    slot_start = panel_start.replace(minute=start_minute, second=0, microsecond=0)
    if slot_start < start_dt:
        slot_start = start_dt

    duration_minutes = (panel_end - panel_start).total_seconds() / 60.0
    rowspan = max(1, math.ceil(duration_minutes / 30.0))
    return (room_id, slot_start), {
        'panel': panel,
        'rowspan': rowspan,
        'end_dt': slot_start + timedelta(minutes=30 * rowspan),
    }


def _rooms_for_day(display_day):
    rooms_used = []
    panels_for_day = []
    for time_group in display_day['panels_by_time']:
        for panel in time_group['panels']:
            if panel.room_id and panel.room not in rooms_used:
                rooms_used.append(panel.room)
            panels_for_day.append(panel)

    rooms_used = sorted(
        (room for room in rooms_used if room and room.id),
        key=lambda room: room.name,
    )
    return rooms_used, panels_for_day


def _matrix_rows_for_day(day_date, rooms_used, panels_for_day, start_dt, end_dt):
    total_half_hours = int((end_dt - start_dt).total_seconds() // (30 * 60))
    time_slots = [start_dt + timedelta(minutes=30 * i) for i in range(total_half_hours)]

    panel_map = {}
    for panel in panels_for_day:
        entry = _panel_slot_entry(panel, day_date, start_dt)
        if entry:
            panel_map[entry[0]] = entry[1]

    room_span_end = {room.id: start_dt for room in rooms_used}
    matrix_rows = []
    for slot in time_slots:
        row = {'time': slot.time(), 'cells': []}
        for room in rooms_used:
            if slot < room_span_end.get(room.id, start_dt):
                row['cells'].append({'type': 'skip'})
                continue

            panel_entry = panel_map.get((room.id, slot))
            if panel_entry:
                row['cells'].append({
                    'type': 'panel',
                    'panel': panel_entry['panel'],
                    'rowspan': panel_entry['rowspan'],
                })
                room_span_end[room.id] = slot + timedelta(minutes=30 * panel_entry['rowspan'])
            else:
                row['cells'].append({'type': 'empty'})
        matrix_rows.append(row)

    return matrix_rows


def build_days_matrix(display_days_with_panels):
    """Build a 2D grid (time slots x rooms) with rowspan for multi-slot panels."""
    days_matrix = []

    for display_day in display_days_with_panels:
        day_obj = display_day['original_day_obj']
        if not day_obj:
            continue

        rooms_used, panels_for_day = _rooms_for_day(display_day)
        day_date = day_obj.date
        start_dt, end_dt = _round_grid_bounds(day_date, panels_for_day)
        matrix_rows = _matrix_rows_for_day(day_date, rooms_used, panels_for_day, start_dt, end_dt)

        days_matrix.append({
            'day': day_obj,
            'rows': matrix_rows,
            'rooms': rooms_used,
        })

    return days_matrix
