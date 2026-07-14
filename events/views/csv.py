import csv
from datetime import datetime

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..auth import organizer_required
from ..forms import CSVImportForm
from ..models import Convention, ConventionDay, Panel, PanelHost, PanelHostOrder, Room, Tag
from ..rsvp import filter_panels_for_user_rsvp
from .admin import _admin_panel_redirect

@organizer_required
def import_panels_csv(request, convention_pk):
    convention = get_object_or_404(Convention, pk=convention_pk)
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            convention = form.cleaned_data['convention']
            
            # Read the CSV file
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            
            # Map of possible column names to their canonical form
            column_mapping = {
                'title': ['title', 'Title'],
                'description': ['description', 'Description'],
                'date': ['date', 'Date'],
                'start_time': ['start time', 'Start Time', 'start_time'],
                'end_time': ['end time', 'End Time', 'end_time'],
                'room': ['room', 'Room'],
                'tags': ['tags', 'Tags'],
                'hosts': ['hosts', 'Hosts']
            }
            
            # Create a mapping of actual column names to canonical names
            actual_to_canonical = {}
            for canonical, possible_names in column_mapping.items():
                for name in possible_names:
                    if name in reader.fieldnames:
                        actual_to_canonical[name] = canonical
                        break
            
            # Check for missing required columns
            required_columns = ['title', 'description', 'date', 'start_time', 'end_time', 'room']
            missing_columns = [col for col in required_columns if col not in actual_to_canonical.values()]
            
            if missing_columns:
                messages.error(request, f"Missing required columns in CSV file: {', '.join(missing_columns)}")
                messages.info(request, "Required columns are: Title, Description, Date, Start Time, End Time, Room")
                messages.info(request, "Optional columns are: Tags, Hosts")
                return render(request, 'events/import_panels.html', {
                    'form': form,
                    'convention': convention,
                    'current_convention_name': convention.name
                })
            
            success_count = 0
            error_count = 0
            errors = []
            
            # Define possible date formats
            date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
            
            for row in reader:
                try:
                    # Debug logging for date field
                    print(f"Processing row {reader.line_num}")
                    
                    # Map the row data to canonical column names
                    mapped_row = {}
                    for actual_name, value in row.items():
                        if actual_name in actual_to_canonical:
                            mapped_row[actual_to_canonical[actual_name]] = value
                    
                    print(f"Raw date value: '{mapped_row.get('date', '')}'")
                    
                    # Clean the date value
                    date_str = mapped_row['date'].strip()
                    if not date_str:
                        raise ValueError("Empty date value")
                    
                    # Try different date formats
                    date = None
                    for date_format in date_formats:
                        try:
                            date = datetime.strptime(date_str, date_format).date()
                            print(f"Successfully parsed date '{date_str}' using format '{date_format}'")
                            break
                        except ValueError as e:
                            print(f"Failed to parse date '{date_str}' using format '{date_format}': {str(e)}")
                            continue
                    
                    if date is None:
                        raise ValueError(f"Invalid date format: '{date_str}'. Supported formats are: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, YYYY/MM/DD")
                    
                    # Parse times
                    try:
                        start_time = datetime.strptime(mapped_row['start_time'].strip(), '%H:%M').time()
                    except ValueError:
                        raise ValueError(f"Invalid start time format: '{mapped_row['start_time']}'. Use HH:MM format (e.g., 14:30)")
                    
                    try:
                        end_time = datetime.strptime(mapped_row['end_time'].strip(), '%H:%M').time()
                    except ValueError:
                        raise ValueError(f"Invalid end time format: '{mapped_row['end_time']}'. Use HH:MM format (e.g., 15:30)")
                    
                    # Validate required fields
                    required_fields = ['title', 'description', 'room']
                    for field in required_fields:
                        if not mapped_row.get(field) or not mapped_row[field].strip():
                            raise ValueError(f"Missing required field: {field}")
                    
                    # Get or create convention day
                    convention_day, _ = ConventionDay.objects.get_or_create(
                        convention=convention,
                        date=date
                    )
                    
                    # Get or create room
                    room, _ = Room.objects.get_or_create(
                        name=mapped_row['room'].strip(),
                        convention=convention
                    )
                    
                    # Create panel
                    panel = Panel.objects.create(
                        title=mapped_row['title'].strip(),
                        description=mapped_row['description'].strip(),
                        convention_day=convention_day,
                        start_time=start_time,
                        end_time=end_time,
                        room=room
                    )
                    
                    # Add tags
                    if mapped_row.get('tags'):
                        tag_names = [tag.strip() for tag in mapped_row['tags'].split(',')]
                        for tag_name in tag_names:
                            if tag_name:  # Only create tag if name is not empty
                                tag, _ = Tag.objects.get_or_create(name=tag_name)
                                panel.tags.add(tag)
                    
                    # Add hosts
                    if mapped_row.get('hosts'):
                        host_names = [host.strip() for host in mapped_row['hosts'].split(',')]
                        for index, host_name in enumerate(host_names):
                            if host_name:  # Only create host if name is not empty
                                host, _ = PanelHost.objects.get_or_create(name=host_name)
                                panel.host.add(host)
                                PanelHostOrder.objects.create(
                                    panel=panel,
                                    host=host,
                                    priority=index
                                )
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_msg = f"Error in row {reader.line_num}: {str(e)}"
                    print(error_msg)  # Debug logging
                    errors.append(error_msg)
            
            if success_count > 0:
                messages.success(request, f'Successfully imported {success_count} panels.')
            if error_count > 0:
                messages.error(request, f'Failed to import {error_count} panels. See details below.')
                for error in errors:
                    messages.error(request, error)
            
            return redirect('events:convention_detail', pk=convention.pk)
    else:
        form = CSVImportForm(initial={'convention': convention})
    
    return render(request, 'events/import_panels.html', {
        'form': form,
        'convention': convention,
        'current_convention_name': convention.name
    })


def export_panels_csv(request, convention_pk):
    convention = get_object_or_404(Convention, pk=convention_pk)
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{convention.name}_schedule.csv"'
    
    # Create CSV writer with custom formatting
    writer = csv.writer(response, quoting=csv.QUOTE_ALL, lineterminator='\n')
    
    # Write header row with proper spacing
    writer.writerow([
        'Title',
        'Description',
        'Date',
        'Start Time',
        'End Time',
        'Room',
        'Tags',
        'Hosts'
    ])
    
    panels = Panel.objects.filter(
        convention_day__convention=convention
    ).select_related(
        'convention_day',
        'room'
    ).prefetch_related(
        'tags',
        'host'
    ).order_by('convention_day__date', 'start_time')

    rsvp_param = request.GET.get('rsvp')
    if rsvp_param:
        panels = filter_panels_for_user_rsvp(panels, request, rsvp_param)
    
    # Write panel data
    for panel in panels:
        # Get tags and hosts as comma-separated strings with proper spacing
        tags = ', '.join(tag.name.strip() for tag in panel.tags.all())
        hosts = ', '.join(host.name.strip() for host in panel.host.all().order_by('panelhostorder__priority'))
        
        # Clean and format the description
        description = panel.description.strip().replace('\n', ' ').replace('\r', '')
        
        writer.writerow([
            panel.title.strip(),
            description,
            panel.convention_day.date.strftime('%Y-%m-%d'),
            panel.start_time.strftime('%H:%M'),
            panel.end_time.strftime('%H:%M'),
            panel.room.name.strip() if panel.room else '',
            tags,
            hosts
        ])
    
    return response


@organizer_required
def download_rooms_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="rooms_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['name'])
    writer.writerow(['Main Hall'])
    writer.writerow(['Panel Room 1'])
    writer.writerow(['Grand Ballroom'])
    return response


@organizer_required
def download_hosts_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="hosts_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['name'])
    writer.writerow(['John Doe'])
    writer.writerow(['Jane Smith'])
    writer.writerow(['DJ FurMix'])
    return response


@organizer_required
def download_tags_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tags_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['name', 'color'])
    writer.writerow(['Art', '#FF6B6B'])
    writer.writerow(['Workshop', '#4ECDC4'])
    writer.writerow(['Performance', '#FFE66D'])
    writer.writerow(['Gaming', '#95E1D3'])
    return response


@organizer_required
def import_rooms_csv(request, convention_pk):
    convention = get_object_or_404(Convention, pk=convention_pk)
    if request.method == 'POST' and request.FILES.get('csv_file'):
        try:
            decoded_file = request.FILES['csv_file'].read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            created_count = 0
            updated_count = 0
            with transaction.atomic():
                for row in reader:
                    name = row.get('name', '').strip()
                    if not name:
                        continue
                    _, created = Room.objects.get_or_create(name=name, convention=convention)
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
            messages.success(
                request,
                f'Successfully imported rooms: {created_count} created, {updated_count} already existed.',
            )
        except Exception as e:
            messages.error(request, f'Error importing rooms: {str(e)}')
    return _admin_panel_redirect(convention_pk, 'rooms')


@organizer_required
def import_hosts_csv(request, convention_pk):
    get_object_or_404(Convention, pk=convention_pk)
    if request.method == 'POST' and request.FILES.get('csv_file'):
        try:
            decoded_file = request.FILES['csv_file'].read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            created_count = 0
            updated_count = 0
            with transaction.atomic():
                for row in reader:
                    name = row.get('name', '').strip()
                    if not name:
                        continue
                    _, created = PanelHost.objects.get_or_create(name=name)
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
            messages.success(
                request,
                f'Successfully imported hosts: {created_count} created, {updated_count} already existed.',
            )
        except Exception as e:
            messages.error(request, f'Error importing hosts: {str(e)}')
    return _admin_panel_redirect(convention_pk, 'hosts')


@organizer_required
def import_tags_csv(request, convention_pk):
    get_object_or_404(Convention, pk=convention_pk)
    if request.method == 'POST' and request.FILES.get('csv_file'):
        try:
            decoded_file = request.FILES['csv_file'].read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            created_count = 0
            updated_count = 0
            with transaction.atomic():
                for row in reader:
                    name = row.get('name', '').strip()
                    color = row.get('color', '').strip() or '#6c757d'
                    if not name:
                        continue
                    tag, created = Tag.objects.get_or_create(name=name, defaults={'color': color})
                    if not created and color:
                        tag.color = color
                        tag.save()
                        updated_count += 1
                    elif created:
                        created_count += 1
            messages.success(
                request,
                f'Successfully imported tags: {created_count} created, {updated_count} updated.',
            )
        except Exception as e:
            messages.error(request, f'Error importing tags: {str(e)}')
    return _admin_panel_redirect(convention_pk, 'tags')
