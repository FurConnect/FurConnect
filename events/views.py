from datetime import timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import logout, authenticate, login
from django.http import JsonResponse, HttpResponse
from django.http import Http404
from .models import Convention, ConventionDay, Panel, Tag, PanelHost, Room, PanelTag, PanelHostOrder
from .forms import ConventionForm, ConventionDayForm, PanelForm, PanelHostForm, TagForm
import icalendar
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Prefetch

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('events:schedule')

def is_admin(user):
    return user.is_staff

def schedule(request):
    convention = Convention.objects.first()
    if convention:
        return redirect('events:convention_detail', pk=convention.pk)
    return render(request, 'events/schedule.html', {'conventions': [], 'current_convention_name': 'FurConnect'})

def convention_detail(request, pk):
    try:
        convention = get_object_or_404(Convention, pk=pk)
        # Pass the convention name to the context
        current_convention_name = convention.name
        
        # Get all unique tags for panels in this convention
        unique_tags = Tag.objects.filter(panels__convention_day__convention=convention).distinct()

        # Get all unique rooms for panels in this convention
        unique_rooms = Room.objects.filter(panels__convention_day__convention=convention).distinct()

        # --- Calculations for timetable display ---
        # Assuming hour_height_px is 80 as in the CSS (consistent with template)
        hour_height_px = 80

        # Pre-calculate panel display properties
        # Order related hosts by name
        days = convention.days.all().prefetch_related(
            'panels__tags', 
            'panels__room'
        )

        # Create a dictionary to hold panels grouped by display day and start time
        panels_by_display_time = {}

        for day in days:
            # Sort panels for the current day by start time
            sorted_panels = day.panels.all().order_by('start_time')

            # Initialize grouping for the current day
            panels_by_display_time[day.date] = {}

            # Group panels by exact start time
            for panel in sorted_panels:
                start_time = panel.start_time

                # Get hosts ordered by their priority in PanelHostOrder
                panel.ordered_hosts = list(panel.host.all().order_by('panelhostorder__priority'))
                
                # Get tags ordered by their priority in PanelTag
                panel.ordered_tags = list(panel.tags.all().order_by('paneltag__priority'))

                # Add panel to the grouped dictionary
                if start_time not in panels_by_display_time[day.date]:
                    panels_by_display_time[day.date][start_time] = []

                panels_by_display_time[day.date][start_time].append(panel)

        # Sort the days for displaying in the template
        sorted_display_days = sorted(panels_by_display_time.keys())
        
        # Reconstruct days structure with panels grouped by display start time
        display_days_with_panels = []
        for d in sorted_display_days:
            # Find the original ConventionDay object for the date
            original_day_obj = next((day for day in convention.days.all() if day.date == d), None)
            if original_day_obj:
                 # Sort the start times for the current day
                 sorted_start_times = sorted(panels_by_display_time[d].keys())
                 panels_at_times = []
                 for start_time in sorted_start_times:
                     panels_at_times.append({
                         'start_time': start_time,
                         'panels': panels_by_display_time[d][start_time]
                     })

                 display_days_with_panels.append({
                     'date': d,
                     'panels_by_time': panels_at_times, # Changed key name to reflect grouping by time
                     'original_day_obj': original_day_obj # Include original object for other template needs
                 })

    except Http404:
        messages.info(request, "The requested convention was not found. Please create a new one.")
        return redirect('events:convention_create')

    return render(request, 'events/convention_detail.html', {
        'convention': convention,
        'days': display_days_with_panels, # Pass the modified structure
        'current_convention_name': current_convention_name,
        'unique_tags': unique_tags, # Pass unique tags to the template
        'unique_rooms': unique_rooms, # Pass unique rooms to the template
        'is_staff': request.user.is_staff, # Pass is_staff status to the template
    })

@login_required
def convention_create(request):
    if request.method == 'POST':
        form = ConventionForm(request.POST)
        if form.is_valid():
            convention = form.save()
            messages.success(request, 'Convention created successfully!')
            return redirect('events:schedule')
    else:
        form = ConventionForm()
    
    # Fetch the current convention name for the title, or use a default
    current_convention = Convention.objects.first()
    current_convention_name = current_convention.name if current_convention else 'FurConnect'

    return render(request, 'events/convention_form.html', {
        'form': form,
        'action': 'Create',
        'current_convention_name': current_convention_name
        # 'states_by_country': STATES_BY_COUNTRY  # Commented out as states are handled by text input now
    })

@login_required
def convention_edit(request, pk):
    convention = get_object_or_404(Convention, pk=pk)
    # Fetch the current convention name
    current_convention = convention.name

    if request.method == 'POST':
        form = ConventionForm(request.POST, request.FILES, instance=convention)
        if form.is_valid():
            form.save()
            messages.success(request, 'Convention updated successfully!')
            # Use the pk from the URL arguments for the redirect
            return redirect('events:convention_detail', pk=pk)
    else:
        form = ConventionForm(instance=convention)
    # Use the current convention's name for the title
    current_convention_name = current_convention

    return render(request, 'events/convention_form.html', {
        'form': form,
        'action': 'Edit',
        'current_convention_name': current_convention_name
    })

@login_required
def panel_create(request, day_pk):
    # Get the ConventionDay using the provided day_pk from the URL
    convention_day_from_url = get_object_or_404(ConventionDay, pk=day_pk)
    # Get the convention associated with this day
    current_convention = convention_day_from_url.convention
    current_convention_name = current_convention.name if current_convention else 'FurConnect'

    # Instantiate the host form here so it's always available
    host_form = PanelHostForm()

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    print(f"Is AJAX request: {is_ajax}")

    if request.method == 'POST':
        # Pass the convention to the form to filter the convention_day queryset
        form = PanelForm(request.POST, convention=current_convention)
        if form.is_valid():
            panel = form.save(commit=False)
            # The convention_day is now selected via the form, no need to set it from URL pk
            panel.save()
            form.save_m2m() # Save ManyToMany data
            messages.success(request, 'Panel created successfully!')

            if is_ajax:
                 # Always return JSON for AJAX success
                 return JsonResponse({'success': True, 'redirect_url': redirect('events:convention_detail', pk=panel.convention_day.convention.pk).url})
            else:
                 # Redirect for non-AJAX success
                 return redirect('events:convention_detail', pk=panel.convention_day.convention.pk)
        else:
            # If form is invalid
            if is_ajax:
                 # Return JSON response with errors
                 return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            else:
                 # For non-AJAX, render the template with errors
                 return render(request, 'events/panel_form.html', {
                     'form': form,
                     'host_form': host_form,
                     'convention': current_convention,
                     'current_convention_name': current_convention_name,
                     'convention_pk': current_convention.pk
                 })
    else:
        # Pass the convention to the form to filter the convention_day queryset
        form = PanelForm(convention=current_convention)

    return render(request, 'events/panel_form.html', {
        'form': form,
        'host_form': host_form, # Pass the host form to the template
        'convention': current_convention, # Pass the convention object
        # 'date': convention_day.date, # No longer needed as day is selected in form
        'current_convention_name': current_convention_name,
        'convention_pk': current_convention.pk # Pass convention pk for redirect if needed
    })

@login_required
def panel_edit(request, pk):
    panel = get_object_or_404(Panel.objects.select_related('convention_day__convention').prefetch_related('tags', 'host'), pk=pk)
    # Store the convention_pk before saving, in case the object state changes
    convention_pk = panel.convention_day.convention.pk
    # Fetch the current convention name
    current_convention = panel.convention_day.convention
    current_convention_name = current_convention.name if current_convention else 'FurConnect'

    # Add ordered hosts and tags to the panel object
    panel.ordered_hosts = panel.get_ordered_hosts()
    panel.ordered_tags = panel.tags.all().order_by('paneltag__priority')

    if request.method == 'POST':
        form = PanelForm(request.POST, instance=panel)
        if form.is_valid():
            panel = form.save()
            messages.success(request, 'Panel updated successfully!')
            # Use the stored convention_pk for the redirect
            return redirect('events:convention_detail', pk=convention_pk)
    else:
        form = PanelForm(instance=panel)
        host_form = PanelHostForm() # Instantiate the host form
        tag_form = TagForm() # Instantiate the tag form
    return render(request, 'events/panel_form.html', {
        'form': form,
        'convention': panel.convention_day.convention,
        'date': panel.convention_day.date,
        'current_convention_name': current_convention_name,
        'convention_pk': panel.convention_day.convention.pk,
        'host_form': host_form,
        'tag_form': tag_form
    })

@login_required
def panel_delete(request, pk):
    panel = get_object_or_404(Panel, pk=pk)
    convention_pk = panel.convention_day.convention.pk
    
    if request.method == 'POST':
        panel.delete()
        messages.success(request, 'Panel deleted successfully!')
        return redirect('events:convention_detail', pk=convention_pk)
    
    return render(request, 'events/panel_confirm_delete.html', {
        'panel': panel,
        'current_convention_name': panel.convention_day.convention.name
    })

@login_required
@user_passes_test(is_admin)
def convention_delete(request, pk):
    convention = get_object_or_404(Convention, pk=pk)
    if request.method == 'POST':
        convention.delete()
        messages.success(request, 'Convention deleted successfully!')
        return redirect('events:schedule')
    # Optional: Add a GET request handler to show a confirmation page
    # else:
    #     return render(request, 'events/convention_confirm_delete.html', {'convention': convention})

def panel_detail_modal_view(request, pk):
    panel = get_object_or_404(Panel.objects.select_related('convention_day__convention').prefetch_related('tags', 'host'), pk=pk)
    # Add ordered hosts and tags to the panel object
    panel.ordered_hosts = list(panel.host.all().order_by('panelhostorder__priority'))
    panel.ordered_tags = list(panel.tags.all().order_by('paneltag__priority'))
    return render(request, 'events/panel_detail_modal.html', {'panel': panel})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Welcome back! You have been successfully logged in.')
            # Redirect to the schedule page on successful login
            return redirect('events:schedule')
        else:
            # Add an error message using Django's messages framework
            messages.error(request, 'Invalid username or password.')

    # Handle GET request or failed POST request by rendering the login template
    # If it was a failed POST, the messages framework will include the error.
    return render(request, 'events/login.html', {
        'current_convention_name': 'FurConnect',
        # You might need to pass a flag here if you want to show the register prompt
        # only when there are no users, but let's keep it simple for now.
        # 'show_register_prompt': True # You would determine this logic elsewhere
    })

@login_required
def add_panel_host_ajax(request):
    print("add_panel_host_ajax called")
    if request.method == 'POST':
        host_id = request.POST.get('host_id')
        image_base64 = request.POST.get('image_base64') # Get base64 string
        name = request.POST.get('name')

        print(f"Received POST data - host_id: {host_id}, name: {name}, image_base64 length: {len(image_base64) if image_base64 else 0}")

        if host_id:
            print(f"Attempting to update existing host with ID: {host_id}")
            # If host_id is provided, try to update the existing host
            try:
                host = PanelHost.objects.get(pk=host_id)
                print("Host found.")
                # Update host instance directly with base64 data
                host.name = request.POST.get('name', host.name) # Update name if provided
                print(f"Updating host name to: {host.name}")
                # Only update image if a new base64 string is provided
                if image_base64:
                    print("Updating host image with new base64 data.")
                    host.image = image_base64
                elif image_base64 == '' and host.image: # Handle explicit clearing of image
                    print("Clearing existing host image.")
                    host.image = None
                host.save()
                print("Host updated successfully.")
                return JsonResponse({
                    'success': True, 
                    'host': {
                        'id': host.pk, 
                        'name': host.name, 
                        'profile_picture': host.image if host.image else None
                    }
                })
            except PanelHost.DoesNotExist:
                print("Error: Host not found for update.")
                return JsonResponse({'success': False, 'error': 'Host not found.'}, status=404)
            except Exception as e:
                print(f"Error updating host: {e}")
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
        else:
            print("Attempting to create new host.")
            # If no host_id, create a new host
            # Manually handle base64 image for creation
            host = PanelHost(name=name, image=image_base64 if image_base64 else None)
            try:
                 host.full_clean() # Validate model fields
                 host.save()
                 print("New host created successfully.")
                 return JsonResponse({
                     'success': True,
                     'host': {
                         'id': host.pk,
                         'name': host.name,
                         'profile_picture': host.image if host.image else None
                     }
                 })
            except ValidationError as e:
                print(f"Validation error creating host: {e.message_dict}")
                return JsonResponse({'success': False, 'errors': e.message_dict}, status=400)
            except Exception as e:
                print(f"Error creating host: {e}")
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
    print("Invalid request method.")
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

@login_required
def add_tag_ajax(request):
    if request.method == 'POST':
        tag_id = request.POST.get('tag_id')
        if tag_id:
            # If tag_id is provided, try to update the existing tag
            try:
                tag = Tag.objects.get(pk=tag_id)
                form = TagForm(request.POST, instance=tag)
            except Tag.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Tag not found.'}, status=404)
        else:
            # If no tag_id, create a new tag
            form = TagForm(request.POST)

        if form.is_valid():
            tag = form.save()
            return JsonResponse({'success': True, 'tag': {'id': tag.pk, 'name': tag.name, 'color': tag.color}})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

def panel_calendar(request, pk):
    panel = get_object_or_404(Panel.objects.select_related('convention_day__convention'), pk=pk)
    
    # Create calendar
    cal = icalendar.Calendar()
    cal.add('prodid', '-//FurConnect//Panel Calendar//EN')
    cal.add('version', '2.0')
    
    # Create event
    event = icalendar.Event()
    event.add('summary', panel.title)
    event.add('description', panel.description)
    event.add('location', f"{panel.convention_day.convention.name} - {panel.room}")
    
    # Set start and end times
    start_datetime = datetime.combine(panel.convention_day.date, panel.start_time)
    end_datetime = datetime.combine(panel.convention_day.date, panel.end_time)
    
    # Handle events that end after midnight
    if end_datetime < start_datetime:
        end_datetime += timedelta(days=1)
    
    event.add('dtstart', start_datetime)
    event.add('dtend', end_datetime)
    event.add('dtstamp', timezone.now())
    
    # Add event to calendar
    cal.add_component(event)
    
    # Create response
    response = HttpResponse(cal.to_ical(), content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="{panel.title}.ics"'
    
    return response

@login_required
def tag_edit(request, name):
    try:
        tag = Tag.objects.get(name__iexact=name)
        if request.method == 'POST':
            form = TagForm(request.POST, instance=tag)
            if form.is_valid():
                form.save()
                messages.success(request, 'Tag updated successfully!')
                # Redirect back to the convention detail page, or schedule if tag has no panels
                if tag.panels.exists():
                    return redirect('events:convention_detail', pk=tag.panels.first().convention_day.convention.pk)
                else:
                    # If the tag is not associated with any panels, redirect to the schedule
                    return redirect('events:schedule')
        else:
            form = TagForm(instance=tag)
        
        return render(request, 'events/tag_form.html', {
            'form': form,
            'tag': tag,
            'current_convention_name': 'FurConnect'
        })
    except Tag.DoesNotExist:
        messages.error(request, 'Tag not found.')
        return redirect('events:schedule')

@login_required
def host_edit(request, pk):
    host = get_object_or_404(PanelHost, pk=pk)
    if request.method == 'POST':
        form = PanelHostForm(request.POST, request.FILES, instance=host)
        if form.is_valid():
            form.save()
            messages.success(request, 'Host updated successfully!')
            # Redirect back to the convention detail page, or schedule if host has no panels
            if host.panels.exists():
                return redirect('events:convention_detail', pk=host.panels.first().convention_day.convention.pk)
            else:
                # If the host is not associated with any panels, redirect to the schedule
                return redirect('events:schedule')
    else:
        form = PanelHostForm(instance=host)
    
    return render(request, 'events/host_form.html', {
        'form': form,
        'host': host,
        'current_convention_name': 'FurConnect'
    })

@login_required
def delete_room_ajax(request, pk):
    """
    AJAX view to delete a single Room.
    """
    if request.method == 'POST':
        try:
            room = Room.objects.get(pk=pk)
            room.delete()
            return JsonResponse({'success': True})
        except Room.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Room not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

@login_required
def delete_host_ajax(request, pk):
    """
    AJAX view to delete a single PanelHost.
    """
    if request.method == 'POST':
        try:
            host = PanelHost.objects.get(pk=pk)
            host.delete()
            return JsonResponse({'success': True})
        except PanelHost.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Host not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

@login_required
def get_tag_details_ajax(request, pk):
    """
    AJAX view to get details of a single Tag.
    """
    try:
        tag = Tag.objects.get(pk=pk)
        return JsonResponse({
            'id': tag.pk,
            'name': tag.name,
            'color': tag.color
        })
    except Tag.DoesNotExist:
        return JsonResponse({'error': 'Tag not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def save_room_ajax(request):
    """
    AJAX view to save a new or existing Room.
    """
    if request.method == 'POST':
        try:
            room_id = request.POST.get('room_id')
            name = request.POST.get('name')
            convention_id = request.POST.get('convention_id')

            if not name or not convention_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Name and convention ID are required.'
                }, status=400)

            convention = get_object_or_404(Convention, pk=convention_id)

            if room_id:
                # Update existing room
                room = get_object_or_404(Room, pk=room_id)
                room.name = name
                room.save()
            else:
                # Create new room
                room = Room.objects.create(
                    name=name,
                    convention=convention
                )

            return JsonResponse({
                'success': True,
                'room': {
                    'id': room.pk,
                    'name': room.name
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method.'
    }, status=400)

@login_required
def toggle_cancelled(request, pk):
    """Toggle the cancelled status of a panel."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        panel = get_object_or_404(Panel, pk=pk)
        panel.cancelled = not panel.cancelled
        panel.save()
        
        # Check if the request wants JSON
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'cancelled': panel.cancelled,
                'message': 'Panel cancelled' if panel.cancelled else 'Panel uncancelled'
            })
        
        # For regular browser requests, redirect back to the convention detail page
        return redirect('events:convention_detail', pk=panel.convention_day.convention.pk)
        
    except Exception as e:
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': str(e)}, status=500)
        messages.error(request, f'Error toggling panel status: {str(e)}')
        return redirect('events:convention_detail', pk=panel.convention_day.convention.pk)

@login_required
@user_passes_test(is_admin)
def delete_tag_ajax(request, pk):
    """
    AJAX view to delete a single Tag.
    """
    if request.method == 'POST':
        try:
            tag = Tag.objects.get(pk=pk)
            tag.delete()
            return JsonResponse({'success': True})
        except Tag.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Tag not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

@login_required
def get_host_details_ajax(request, pk):
    """
    AJAX view to get details of a single PanelHost.
    """
    try:
        host = PanelHost.objects.get(pk=pk)
        return JsonResponse({
            'id': host.pk,
            'name': host.name,
            'profile_picture': host.image if host.image else None
        })
    except PanelHost.DoesNotExist:
        return JsonResponse({'error': 'Host not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def get_room_details_ajax(request, pk):
    """
    AJAX view to get details of a single Room.
    """
    try:
        room = Room.objects.get(pk=pk)
        return JsonResponse({
            'id': room.pk,
            'name': room.name
        })
    except Room.DoesNotExist:
        return JsonResponse({'error': 'Room not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def get_all_hosts_ajax(request):
    """
    AJAX view to get all PanelHosts for a given convention.
    Requires convention_id as a GET parameter.
    Optionally accepts panel_id to mark selected hosts.
    """
    convention_id = request.GET.get('convention_id')
    panel_id = request.GET.get('panel_id')

    if not convention_id:
        return JsonResponse({'error': 'convention_id is required.'}, status=400)

    try:
        # Filter hosts by convention and order by name
        hosts = PanelHost.objects.filter(panels__convention_day__convention__id=convention_id).distinct().order_by('name')

        # Determine selected hosts if panel_id is provided
        selected_host_ids = []
        if panel_id:
            try:
                panel = Panel.objects.get(pk=panel_id)
                selected_host_ids = list(panel.host.values_list('id', flat=True))
            except Panel.DoesNotExist:
                pass # Panel not found, no hosts are pre-selected

        hosts_data = []
        for host in hosts:
            hosts_data.append({
                'id': host.pk,
                'name': host.name,
                'profile_picture': host.image if host.image else None,
                'selected': host.id in selected_host_ids
            })

        return JsonResponse({'hosts': hosts_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def get_all_rooms_ajax(request):
    """
    AJAX view to get all Rooms for a given convention.
    Requires convention_id as a GET parameter.
    """
    convention_id = request.GET.get('convention_id')

    if not convention_id:
        return JsonResponse({'error': 'convention_id is required.'}, status=400)

    try:
        rooms = Room.objects.filter(convention__id=convention_id)
        rooms_data = []
        for room in rooms:
            rooms_data.append({
                'id': room.pk,
                'name': room.name
            })
        return JsonResponse({'rooms': rooms_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def get_all_tags_ajax(request):
    """
    AJAX view to get all Tags for a given convention.
    Requires convention_id as a GET parameter.
    """
    convention_id = request.GET.get('convention_id')

    if not convention_id:
        return JsonResponse({'error': 'convention_id is required.'}, status=400)

    try:
        # Filter tags by convention (assuming Tag has a link to Convention, e.g., through Panels)
        # This might need adjustment based on your actual model relationships
        # Assuming a tag is related to a convention via a panel
        tags = Tag.objects.filter(panels__convention_day__convention__id=convention_id).distinct()

        tags_data = []
        for tag in tags:
            tags_data.append({
                'id': tag.pk,
                'name': tag.name,
                'color': tag.color
            })
        return JsonResponse({'tags': tags_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def reorder_tags_ajax(request, panel_id):
    """
    AJAX view to reorder tags for a panel.
    Expects a POST request with a list of tag IDs in the desired order.
    """
    if request.method == 'POST':
        try:
            panel = Panel.objects.get(pk=panel_id)
            tag_ids = request.POST.getlist('tag_ids[]')
            
            # Update priorities for each tag
            for index, tag_id in enumerate(tag_ids):
                PanelTag.objects.filter(panel=panel, tag_id=tag_id).update(priority=index)
            
            return JsonResponse({'success': True})
        except Panel.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Panel not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

@login_required
def reorder_hosts_ajax(request, panel_id):
    """
    AJAX view to reorder hosts for a panel.
    Expects a POST request with a list of host IDs in the desired order.
    """
    if request.method == 'POST':
        try:
            panel = Panel.objects.get(pk=panel_id)
            host_ids = request.POST.getlist('host_ids[]')
            
            # Update priorities for each host
            for index, host_id in enumerate(host_ids):
                PanelHostOrder.objects.filter(panel=panel, host_id=host_id).update(priority=index)
            
            return JsonResponse({'success': True})
        except Panel.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Panel not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)
