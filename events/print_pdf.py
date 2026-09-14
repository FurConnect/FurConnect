from io import BytesIO
import base64

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import Convention
from .rsvp import filter_panels_for_user_rsvp

BRAND = colors.HexColor('#111111')
BRAND_SOFT = colors.HexColor('#f2f2f2')
BRAND_MID = colors.HexColor('#555555')
INK = colors.HexColor('#111111')
MUTED = colors.HexColor('#666666')
LINE = colors.HexColor('#cccccc')
PAGE_BG = colors.HexColor('#fafafa')
WHITE = colors.white

# Landscape letter frame is ~536pt tall; keep each table under that.
GRID_HEADER_HEIGHT = 18
GRID_ROW_HEIGHT = 30
GRID_MAX_BODY_SLOTS = 12
GRID_SLOT_MINUTES = 30


def _hex_color(value, fallback='#111111'):
    raw = (value or fallback or '#111111').lstrip('#')
    if len(raw) != 6:
        raw = fallback.lstrip('#')
    try:
        return colors.HexColor(f'#{raw}')
    except Exception:
        return colors.HexColor(fallback)


def _contrast_hex(accent):
    color = (accent or '').lstrip('#')
    if len(color) != 6:
        return '#111111'
    try:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
    except ValueError:
        return '#111111'
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return '#111111' if luminance > 0.55 else '#f8f9fa'


def _fmt_time(value):
    try:
        return value.strftime('%-I:%M %p')
    except ValueError:
        return value.strftime('%I:%M %p').lstrip('0')


def _truncate(text, limit=90):
    cleaned = ' '.join((text or '').split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + '...'


def _escape(text):
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _panel_accent(panel):
    tags = list(panel.tags.all().order_by('paneltag__priority'))
    if tags and tags[0].color:
        return tags[0].color
    return '#ffc107'


def _soft_tint(hex_value, amount=0.82):
    """Blend accent toward white for soft card header backgrounds."""
    raw = (hex_value or '#ffc107').lstrip('#')
    if len(raw) != 6:
        raw = 'ffc107'
    try:
        r = int(raw[0:2], 16)
        g = int(raw[2:4], 16)
        b = int(raw[4:6], 16)
    except ValueError:
        return colors.HexColor('#fff8e1')
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return colors.HexColor(f'#{r:02x}{g:02x}{b:02x}')


def _desc_two_lines(text, width_chars=72):
    """Keep about two wrapped lines of description for grid cells."""
    cleaned = ' '.join((text or '').split())
    if not cleaned:
        return ''
    limit = width_chars * 2
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + '...'


def _panel_hosts(panel):
    return ', '.join(
        h.name for h in panel.host.all().order_by('panelhostorder__priority')
    )


def _add_banner(elements, convention, max_width):
    if not (convention.banner_image and convention.banner_image.startswith('data:image')):
        return
    try:
        _header, b64data = convention.banner_image.split(',', 1)
        img_stream = BytesIO(base64.b64decode(b64data))
        banner = RLImage(img_stream, width=max_width, height=72, kind='proportional')
        elements.append(banner)
        elements.append(Spacer(1, 10))
    except Exception:
        pass


def _page_number(canvas, doc):
    page_num = canvas.getPageNumber()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(BRAND_MID)
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 16, f'Page {page_num}')
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 28, doc.pagesize[0] - doc.rightMargin, 28)


def _build_list_elements(convention, days, rsvp_param, request, styles):
    elements = []
    title_style = ParagraphStyle(
        'ListTitle',
        parent=styles['Title'],
        textColor=BRAND,
        fontSize=22,
        spaceAfter=6,
    )
    elements.append(Paragraph(f'<b>{convention.name}</b>', title_style))
    _add_banner(elements, convention, 480)
    elements.append(Spacer(1, 12))

    day_style = ParagraphStyle(
        'DayHeading',
        parent=styles['Heading2'],
        textColor=INK,
        alignment=TA_CENTER,
        fontSize=14,
        spaceBefore=8,
        spaceAfter=10,
    )
    card_width = 540

    for day in days:
        elements.append(Paragraph(day.date.strftime('%A, %B %d, %Y'), day_style))
        panels_qs = day.panels.all().order_by('start_time')
        if rsvp_param:
            panels_qs = filter_panels_for_user_rsvp(panels_qs, request, rsvp_param).order_by('start_time')
        panels = list(panels_qs)
        if not panels:
            elements.append(Paragraph('<i>No panels scheduled.</i>', styles['Normal']))
            elements.append(Spacer(1, 12))
            continue

        for panel in panels:
            hosts = _panel_hosts(panel)
            tags = ', '.join(t.name for t in panel.tags.all().order_by('paneltag__priority'))
            accent = _panel_accent(panel)
            title_bits = _escape(panel.title)
            if panel.cancelled:
                title_bits = f'[Cancelled] {title_bits}'
            card_data = [
                [Paragraph(
                    f"<b><font color='{accent}' size='12'>{title_bits}</font></b>",
                    styles['Normal'],
                )],
                [Paragraph(
                    f"<b>Time:</b> {_fmt_time(panel.start_time)} - {_fmt_time(panel.end_time)}",
                    styles['Normal'],
                )],
                [Paragraph(
                    f"<b>Room:</b> {_escape(panel.room.name if panel.room else 'N/A')}",
                    styles['Normal'],
                )],
                [Paragraph(f"<b>Host(s):</b> {_escape(hosts) or 'N/A'}", styles['Normal'])],
                [Paragraph(f"<b>Tag(s):</b> {_escape(tags) or 'N/A'}", styles['Normal'])],
            ]
            if panel.description:
                card_data.append([Paragraph(_escape(_truncate(panel.description, 280)), styles['Normal'])])
            card = Table(card_data, colWidths=[card_width])
            card.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1.2, _hex_color(accent)),
                ('BACKGROUND', (0, 0), (-1, 0), _soft_tint(accent)),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ]))
            elements.append(card)
            elements.append(Spacer(1, 14))

    return elements


def _time_to_minutes(value):
    return value.hour * 60 + value.minute


def _minutes_to_label(minutes):
    hours = (minutes // 60) % 24
    mins = minutes % 60
    suffix = 'AM' if hours < 12 else 'PM'
    h12 = hours % 12 or 12
    if mins:
        return f'{h12}:{mins:02d} {suffix}'
    return f'{h12} {suffix}'


def _slot_index(minutes, grid_start, slot_minutes):
    return max(0, (minutes - grid_start) // slot_minutes)


def _collect_rooms(panels):
    rooms = []
    seen = set()
    for panel in panels:
        if panel.room_id and panel.room and panel.room_id not in seen:
            rooms.append(panel.room)
            seen.add(panel.room_id)
    rooms.sort(key=lambda room: (room.sort_order, room.name or '', room.id))
    return rooms


def _build_placements(panels, rooms, grid_start, slot_count, slot_minutes):
    room_index = {room.id: idx for idx, room in enumerate(rooms)}
    occupancy = [[None for _ in rooms] for _ in range(slot_count)]
    placements = []

    ordered = sorted(
        panels,
        key=lambda p: (
            _time_to_minutes(p.start_time),
            -(_time_to_minutes(p.end_time) - _time_to_minutes(p.start_time)),
            p.title or '',
        ),
    )

    for panel in ordered:
        if not panel.room_id or panel.room_id not in room_index:
            continue
        room_idx = room_index[panel.room_id]
        start_m = _time_to_minutes(panel.start_time)
        end_m = _time_to_minutes(panel.end_time)
        if end_m <= start_m:
            end_m = start_m + slot_minutes
        start_slot = _slot_index(start_m, grid_start, slot_minutes)
        end_slot = _slot_index(end_m - 1, grid_start, slot_minutes) + 1
        start_slot = min(max(start_slot, 0), slot_count - 1)
        end_slot = min(max(end_slot, start_slot + 1), slot_count)
        span = end_slot - start_slot

        blocked = False
        for s in range(start_slot, end_slot):
            if occupancy[s][room_idx] is not None:
                blocked = True
                break
        if blocked:
            existing_id = occupancy[start_slot][room_idx]
            if existing_id is not None:
                for item in placements:
                    if item['panel'].pk == existing_id and item['room_idx'] == room_idx:
                        item['extras'].append(panel)
                        break
            continue

        for s in range(start_slot, end_slot):
            occupancy[s][room_idx] = panel.pk
        placements.append({
            'panel': panel,
            'room_idx': room_idx,
            'start_slot': start_slot,
            'span': span,
            'extras': [],
        })

    return placements


def _panel_cell_paragraph(panel, extras, styles, span_slots, continued=False):
    accent = _panel_accent(panel)
    text_hex = _contrast_hex(accent)
    title = panel.title or ''
    if panel.cancelled:
        title = f'[Cancelled] {title}'
    elif panel.is_featured:
        title = f'* {title}'
    if continued:
        title = f'(cont.) {title}'

    lines = [f'<b>{_escape(title)}</b>']
    lines.append(f'{_fmt_time(panel.start_time)} - {_fmt_time(panel.end_time)}')

    if not continued and panel.description:
        # Aim for ~2 wrapped lines; shorten on single-slot cells.
        width_chars = 40 if span_slots <= 1 else 56
        desc = _desc_two_lines(panel.description, width_chars=width_chars)
        if span_slots <= 1:
            desc = _truncate(desc, 48)
        if desc:
            lines.append(_escape(desc))

    for extra in extras[:1]:
        extra_title = extra.title or ''
        if extra.cancelled:
            extra_title = f'[Cancelled] {extra_title}'
        lines.append(f'+ {_escape(_truncate(extra_title, 32))}')

    cell_style = ParagraphStyle(
        f'CellBody{panel.pk}_{int(continued)}',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor(text_hex),
        alignment=TA_LEFT,
    )
    return Paragraph('<br/>'.join(lines), cell_style), accent


def _build_grid_chunk_table(
    rooms,
    styles,
    usable_width,
    grid_start,
    slot_minutes,
    chunk_start,
    chunk_slots,
    placements,
):
    """Build one page-sized grid chunk covering absolute slots [chunk_start, chunk_start+chunk_slots)."""
    time_col = 0.75 * inch
    room_col = max(1.0 * inch, (usable_width - time_col) / max(len(rooms), 1))
    col_widths = [time_col] + [room_col] * len(rooms)

    header_style = ParagraphStyle(
        'GridHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=WHITE,
        alignment=TA_CENTER,
        leading=10,
    )
    time_style = ParagraphStyle(
        'GridTime',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        textColor=BRAND,
        alignment=TA_CENTER,
        leading=8,
    )

    header = [Paragraph('Time', header_style)] + [
        Paragraph(_escape(room.name), header_style) for room in rooms
    ]
    data = [header]
    for local_slot in range(chunk_slots):
        absolute_slot = chunk_start + local_slot
        label = _minutes_to_label(grid_start + absolute_slot * slot_minutes)
        data.append([Paragraph(label, time_style)] + [''] * len(rooms))

    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), BRAND),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('BACKGROUND', (0, 1), (0, -1), BRAND_SOFT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.4, LINE),
        ('BOX', (0, 0), (-1, -1), 1.0, BRAND),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (1, 1), (-1, -1), [WHITE, PAGE_BG]),
    ]

    chunk_end = chunk_start + chunk_slots
    for item in placements:
        start = item['start_slot']
        end = start + item['span']
        if end <= chunk_start or start >= chunk_end:
            continue

        clipped_start = max(start, chunk_start)
        clipped_end = min(end, chunk_end)
        local_start = clipped_start - chunk_start
        local_span = clipped_end - clipped_start
        if local_span < 1:
            continue

        col = item['room_idx'] + 1
        row = local_start + 1
        continued = clipped_start > start
        cell, accent = _panel_cell_paragraph(
            item['panel'],
            item['extras'] if not continued else [],
            styles,
            local_span,
            continued=continued,
        )
        data[row][col] = cell
        if local_span > 1:
            style_commands.append(('SPAN', (col, row), (col, row + local_span - 1)))
            for s in range(1, local_span):
                data[row + s][col] = ''
        style_commands.append(
            ('BACKGROUND', (col, row), (col, row + local_span - 1), _hex_color(accent))
        )
        style_commands.append(
            ('BOX', (col, row), (col, row + local_span - 1), 0.8, _hex_color(accent))
        )
        style_commands.append(('VALIGN', (col, row), (col, row + local_span - 1), 'TOP'))

    row_heights = [GRID_HEADER_HEIGHT] + [GRID_ROW_HEIGHT] * chunk_slots
    table = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
    table.setStyle(TableStyle(style_commands))
    # Prevent ReportLab from trying (and failing) to split SPAN tables mid-page.
    table._splitByRow = 0
    return table


def _build_day_grid_tables(panels, styles, usable_width):
    rooms = _collect_rooms(panels)
    if not rooms:
        return [Paragraph('<i>No roomed panels scheduled.</i>', styles['Normal'])]

    slot_minutes = GRID_SLOT_MINUTES
    starts = [_time_to_minutes(p.start_time) for p in panels]
    ends = []
    for panel in panels:
        start_m = _time_to_minutes(panel.start_time)
        end_m = _time_to_minutes(panel.end_time)
        if end_m <= start_m:
            end_m = start_m + slot_minutes
        ends.append(end_m)

    grid_start = (min(starts) // 60) * 60
    grid_end = max(ends)
    if grid_end % slot_minutes:
        grid_end += slot_minutes - (grid_end % slot_minutes)
    if grid_end <= grid_start:
        grid_end = grid_start + slot_minutes

    slot_count = max(1, (grid_end - grid_start) // slot_minutes)
    placements = _build_placements(panels, rooms, grid_start, slot_count, slot_minutes)

    tables = []
    for chunk_start in range(0, slot_count, GRID_MAX_BODY_SLOTS):
        chunk_slots = min(GRID_MAX_BODY_SLOTS, slot_count - chunk_start)
        tables.append(
            _build_grid_chunk_table(
                rooms,
                styles,
                usable_width,
                grid_start,
                slot_minutes,
                chunk_start,
                chunk_slots,
                placements,
            )
        )
    return tables


def _build_grid_elements(convention, days, rsvp_param, request, styles, usable_width):
    elements = []
    title_style = ParagraphStyle(
        'GridTitle',
        parent=styles['Title'],
        textColor=BRAND,
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'GridSubtitle',
        parent=styles['Normal'],
        textColor=MUTED,
        fontSize=9,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    day_style = ParagraphStyle(
        'GridDay',
        parent=styles['Heading2'],
        textColor=INK,
        fontSize=12,
        spaceBefore=2,
        spaceAfter=6,
    )

    elements.append(Paragraph(f'<b>{convention.name}</b>', title_style))
    elements.append(Paragraph('Schedule Grid', subtitle_style))
    # Skip large banners on grid exports — they steal vertical space from the table.
    if convention.banner_image and not convention.banner_image.startswith('data:image'):
        pass

    for day in days:
        panels_qs = day.panels.select_related('room').prefetch_related(
            'tags', 'host',
        ).order_by('start_time')
        if rsvp_param:
            panels_qs = filter_panels_for_user_rsvp(panels_qs, request, rsvp_param).order_by('start_time')
        panels = [p for p in panels_qs if p.room_id]

        elements.append(Paragraph(day.date.strftime('%A, %B %d, %Y'), day_style))
        if not panels:
            elements.append(Paragraph('<i>No panels scheduled.</i>', styles['Normal']))
            elements.append(Spacer(1, 10))
            continue

        tables = _build_day_grid_tables(panels, styles, usable_width)
        for idx, table in enumerate(tables):
            elements.append(table)
            if idx < len(tables) - 1:
                elements.append(Spacer(1, 10))
        elements.append(Spacer(1, 14))

    return elements


def printable_schedule_pdf(request, pk):
    convention = get_object_or_404(Convention, pk=pk)
    days = convention.days.all().order_by('date')
    rsvp_param = request.GET.get('rsvp')
    view = (request.GET.get('view') or 'list').lower()
    if view not in ('list', 'grid'):
        view = 'list'

    buffer = BytesIO()
    styles = getSampleStyleSheet()

    if view == 'grid':
        pagesize = landscape(letter)
        doc = SimpleDocTemplate(
            buffer,
            pagesize=pagesize,
            rightMargin=28,
            leftMargin=28,
            topMargin=24,
            bottomMargin=32,
        )
        usable_width = pagesize[0] - doc.leftMargin - doc.rightMargin
        elements = _build_grid_elements(
            convention, days, rsvp_param, request, styles, usable_width,
        )
        filename = f'{convention.name}_schedule_grid.pdf'
    else:
        pagesize = letter
        doc = SimpleDocTemplate(
            buffer,
            pagesize=pagesize,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        elements = _build_list_elements(convention, days, rsvp_param, request, styles)
        filename = f'{convention.name}_schedule.pdf'

    doc.build(elements, onFirstPage=_page_number, onLaterPages=_page_number)
    pdf = buffer.getvalue()
    buffer.close()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="{filename}"'
    return response
