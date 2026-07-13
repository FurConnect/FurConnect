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

        # Always start at the top of the hour so an hour label (e.g. "12")
        # still shows when the earliest panel is xx:30 or later.
        start_dt = datetime.combine(day_date, min_start_time).replace(
            minute=0, second=0, microsecond=0
        )

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


def _floor_to_half_hour(dt):
    """Snap down to the preceding :00 or :30 boundary."""
    midnight = datetime.combine(dt.date(), time(0, 0))
    minutes = int((dt - midnight).total_seconds() // 60)
    return midnight + timedelta(minutes=(minutes // 30) * 30)


def _ceil_to_half_hour(dt):
    """Snap up to the next :00 or :30 boundary (exact boundaries stay put)."""
    midnight = datetime.combine(dt.date(), time(0, 0))
    minutes = (dt - midnight).total_seconds() / 60.0
    return midnight + timedelta(minutes=math.ceil(minutes / 30.0) * 30)


def _panel_slot_entry(panel, day_date, start_dt):
    room_id = panel.room_id
    if not room_id:
        return None

    panel_start = datetime.combine(day_date, panel.start_time)
    panel_end = datetime.combine(day_date, panel.end_time)
    if panel_end <= panel_start:
        panel_end += timedelta(days=1)

    # Place on the half-hour grid using floored start / ceiled end so that
    # anything between xx:00 and xx:30 still occupies the xx:00 slot and
    # spans through every half-hour it covers (duration-from-real-start
    # underspans after start is floored).
    slot_start = _floor_to_half_hour(panel_start)
    if slot_start < start_dt:
        slot_start = start_dt

    slot_end = _ceil_to_half_hour(panel_end)
    if slot_end <= slot_start:
        slot_end = slot_start + timedelta(minutes=30)

    rowspan = max(1, int((slot_end - slot_start).total_seconds() // (30 * 60)))
    slot_minutes = rowspan * 30
    # Offset within the spanned block so e.g. 12:15 sits 1/4 into the hour.
    start_offset_minutes = max(0, (panel_start - slot_start).total_seconds() / 60.0)
    duration_minutes = max(1, (panel_end - panel_start).total_seconds() / 60.0)
    # Keep the card inside the spanned cell if start/end fall on exact boundaries.
    if start_offset_minutes + duration_minutes > slot_minutes:
        duration_minutes = max(1, slot_minutes - start_offset_minutes)

    top_pct = (start_offset_minutes / slot_minutes) * 100.0
    height_pct = (duration_minutes / slot_minutes) * 100.0

    return (room_id, slot_start), {
        'panel': panel,
        'rowspan': rowspan,
        'end_dt': slot_start + timedelta(minutes=30 * rowspan),
        'start_offset_minutes': start_offset_minutes,
        'duration_minutes': duration_minutes,
        'slot_minutes': slot_minutes,
        'top_pct': top_pct,
        'height_pct': height_pct,
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


def _cap_rowspans_for_room(panel_map):
    """Prevent a panel's rowspan from swallowing a later panel in the same room.

    Without this, a panel whose start snapped back into the prior half-hour
    can mark xx:00 as occupied and the real xx:00 (or xx:30) panel is skipped.
    """
    by_room = {}
    for (room_id, slot_start), entry in panel_map.items():
        by_room.setdefault(room_id, []).append((slot_start, entry))

    for room_id, entries in by_room.items():
        entries.sort(key=lambda item: item[0])
        for index, (slot_start, entry) in enumerate(entries):
            if index + 1 >= len(entries):
                continue
            next_start = entries[index + 1][0]
            if entry['end_dt'] <= next_start:
                continue
            rowspan = max(1, int((next_start - slot_start).total_seconds() // (30 * 60)))
            entry['rowspan'] = rowspan
            entry['end_dt'] = slot_start + timedelta(minutes=30 * rowspan)
            slot_minutes = rowspan * 30
            entry['slot_minutes'] = slot_minutes
            start_offset = min(entry.get('start_offset_minutes', 0), max(0, slot_minutes - 1))
            duration = min(entry.get('duration_minutes', slot_minutes), slot_minutes - start_offset)
            entry['start_offset_minutes'] = start_offset
            entry['duration_minutes'] = max(1, duration)
            entry['top_pct'] = (start_offset / slot_minutes) * 100.0
            entry['height_pct'] = (entry['duration_minutes'] / slot_minutes) * 100.0


def _matrix_rows_for_day(day_date, rooms_used, panels_for_day, start_dt, end_dt):
    total_half_hours = int((end_dt - start_dt).total_seconds() // (30 * 60))
    time_slots = [start_dt + timedelta(minutes=30 * i) for i in range(total_half_hours)]

    panel_map = {}
    for panel in panels_for_day:
        entry = _panel_slot_entry(panel, day_date, start_dt)
        if entry:
            # Prefer the longer block if two panels snap to the same slot.
            key, value = entry
            existing = panel_map.get(key)
            if existing is None or value['rowspan'] > existing['rowspan']:
                panel_map[key] = value

    _cap_rowspans_for_room(panel_map)

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
                    'start_offset_minutes': panel_entry.get('start_offset_minutes', 0),
                    'duration_minutes': panel_entry.get('duration_minutes', panel_entry['rowspan'] * 30),
                    'slot_minutes': panel_entry.get('slot_minutes', panel_entry['rowspan'] * 30),
                    'top_pct': panel_entry.get('top_pct', 0),
                    'height_pct': panel_entry.get('height_pct', 100),
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
