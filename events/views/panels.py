from datetime import datetime, timedelta, time
import math

import icalendar
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..auth import can_manage_events, organizer_required
from ..concat import attach_host_avatar_urls
from ..forms import PanelForm, PanelHostForm, TagForm
from ..models import ConventionDay, Panel, PanelHostOrder, PanelTag
from ..rsvp import get_rsvp_context

@organizer_required
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


@organizer_required
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


@organizer_required
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


def panel_detail_modal_view(request, pk):
    panel = get_object_or_404(
        Panel.objects.select_related('convention_day__convention').prefetch_related('tags', 'host', 'rsvps'),
        pk=pk,
    )
    # Add ordered hosts and tags to the panel object
    panel.ordered_hosts = list(panel.host.all().order_by('panelhostorder__priority'))
    panel.ordered_tags = list(panel.tags.all().order_by('paneltag__priority'))
    attach_host_avatar_urls(panel.ordered_hosts)
    context = {'panel': panel}
    context.update(get_rsvp_context(request, panel))
    return render(request, 'events/panel_detail_modal.html', context)


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


@organizer_required
def toggle_cancelled(request, pk):
    """Toggle the cancelled status of a panel."""
    if not can_manage_events(request):
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


@organizer_required
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


@organizer_required
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
