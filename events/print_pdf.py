from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from .models import Convention, Room

def printable_schedule_pdf(request, pk):
    convention = get_object_or_404(Convention, pk=pk)
    days = convention.days.all().order_by('date')
    unique_rooms = Room.objects.filter(convention=convention).order_by('name')
    view = request.GET.get('view', 'grid')

    # List view grouping
    panels_by_display_time = {}
    for day in days:
        sorted_panels = day.panels.all().order_by('start_time')
        panels_by_display_time[day.date] = {}
        for panel in sorted_panels:
            panel.ordered_hosts = list(panel.host.all().order_by('panelhostorder__priority'))
            panel.ordered_tags = list(panel.tags.all().order_by('paneltag__priority'))
            start_time = panel.start_time
            if start_time not in panels_by_display_time[day.date]:
                panels_by_display_time[day.date][start_time] = []
            panels_by_display_time[day.date][start_time].append(panel)
    sorted_display_days = sorted(panels_by_display_time.keys())
    display_days_with_panels = []
    for day_date in sorted_display_days:
        day_obj = days.get(date=day_date)
        display_day = {
            'original_day_obj': day_obj,
            'panels_by_time': []
        }
        sorted_times = sorted(panels_by_display_time[day_date].keys())
        for time in sorted_times:
            display_day['panels_by_time'].append({
                'start_time': time,
                'panels': panels_by_display_time[day_date][time]
            })
        display_days_with_panels.append(display_day)

    # Grid view matrix
    days_matrix = []
    rooms_list = list(unique_rooms)
    for display_day in display_days_with_panels:
        matrix_rows = []
        for time_group in display_day['panels_by_time']:
            row = {
                'time': time_group['start_time'],
                'cells': []
            }
            for room in rooms_list:
                panel_for_room = next(
                    (panel for panel in time_group['panels'] if panel.room and panel.room.name == room.name),
                    None
                )
                row['cells'].append(panel_for_room)
            matrix_rows.append(row)
        days_matrix.append({'day': display_day['original_day_obj'], 'rows': matrix_rows})

    html_string = render_to_string('events/printable_schedule.html', {
        'convention': convention,
        'days': display_days_with_panels,
        'days_matrix': days_matrix,
        'unique_rooms': unique_rooms,
        'view': view
    })
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="{convention.name}_schedule.pdf"'
    return response
