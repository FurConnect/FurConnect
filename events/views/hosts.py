import base64
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from ..auth import organizer_required
from ..concat import apply_host_profile_image, build_avatar_map, resolve_profile_picture, serialize_panel_host
from ..forms import PanelHostForm
from ..models import Convention, Panel, PanelHost

@organizer_required
def add_panel_host_ajax(request):
    print("add_panel_host_ajax called")
    if request.method == 'POST':
        host_id = request.POST.get('host_id')
        image_base64 = request.POST.get('image_base64') # Get base64 string
        name = request.POST.get('name')
        concat_user_id = (request.POST.get('concat_user_id') or '').strip()

        print(f"Received POST data - host_id: {host_id}, name: {name}, image_base64 length: {len(image_base64) if image_base64 else 0}")

        if host_id:
            print(f"Attempting to update existing host with ID: {host_id}")
            try:
                host = PanelHost.objects.get(pk=host_id)
                print("Host found.")
                host.name = request.POST.get('name', host.name)
                print(f"Updating host name to: {host.name}")
                if settings.CONCAT_ENABLED:
                    host.concat_user_id = concat_user_id
                else:
                    host.concat_user_id = ''
                if image_base64:
                    print("Updating host image with new base64 data.")
                elif image_base64 == '' and host.image:
                    print("Clearing existing host image.")
                apply_host_profile_image(host, image_base64)
                host.save()
                print("Host updated successfully.")
                return JsonResponse({
                    'success': True,
                    'host': serialize_panel_host(host),
                })
            except PanelHost.DoesNotExist:
                print("Error: Host not found for update.")
                return JsonResponse({'success': False, 'error': 'Host not found.'}, status=404)
            except Exception as e:
                print(f"Error updating host: {e}")
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
        else:
            print("Attempting to create new host.")
            host = PanelHost(
                name=name,
                concat_user_id=concat_user_id if settings.CONCAT_ENABLED else '',
                image=image_base64 if image_base64 else None,
            )
            try:
                host.full_clean()
                host.save()
                print("New host created successfully.")
                return JsonResponse({
                    'success': True,
                    'host': serialize_panel_host(host),
                })
            except ValidationError as e:
                print(f"Validation error creating host: {e.message_dict}")
                return JsonResponse({'success': False, 'errors': e.message_dict}, status=400)
            except Exception as e:
                print(f"Error creating host: {e}")
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
    print("Invalid request method.")
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)


@organizer_required
def host_edit(request, pk):
    host = get_object_or_404(PanelHost, pk=pk)
    if request.method == 'POST':
        form = PanelHostForm(request.POST, request.FILES, instance=host)
        if form.is_valid():
            host = form.save(commit=False)
            uploaded_image = form.cleaned_data.get('image')
            if uploaded_image:
                mime = uploaded_image.content_type or 'image/jpeg'
                host.image = f'data:{mime};base64,{base64.b64encode(uploaded_image.read()).decode("ascii")}'
            elif request.POST.get('remove_image'):
                host.image = None
            host.save()
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


@organizer_required
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


def _serialize_host_panel(panel):
    tag_color = panel.tags.first().color if panel.tags.exists() else '#ffffff'
    day_date = panel.convention_day.date if panel.convention_day and panel.convention_day.date else None
    return {
        'id': panel.pk,
        'title': panel.title,
        'description': panel.description,
        'start_time': panel.start_time.strftime('%I:%M %p') if panel.start_time else '',
        'end_time': panel.end_time.strftime('%I:%M %p') if panel.end_time else '',
        'room_name': panel.room.name if panel.room else '',
        'tag_color': tag_color,
        'cancelled': panel.cancelled,
        'day_of_week': day_date.strftime('%A') if day_date else '',
        '_sort_date': day_date,
        '_sort_time': panel.start_time,
    }


def _get_host_panels_queryset(host, convention_id=None):
    panels = host.panels.all().select_related('convention_day', 'room').prefetch_related('tags')
    if convention_id:
        panels = panels.filter(convention_day__convention_id=convention_id)
    return panels


def get_host_details_ajax(request, pk):
    """
    AJAX view to get details of a single PanelHost.
    """
    try:
        host = PanelHost.objects.get(pk=pk)
        convention_id = request.GET.get('convention_id')
        panels = _get_host_panels_queryset(host, convention_id)
        panels_data = [_serialize_host_panel(panel) for panel in panels]
        # Sort by day (date), then by time
        panels_data.sort(key=lambda x: (x['_sort_date'], x['_sort_time']))
        for p in panels_data:
            p.pop('_sort_date', None)
            p.pop('_sort_time', None)
        
        return JsonResponse({
            'id': host.pk,
            'name': host.name,
            'concat_user_id': host.concat_user_id,
            'profile_picture': resolve_profile_picture(host),
            'panels': panels_data,
            'panels_count': len(panels_data)
        })
    except PanelHost.DoesNotExist:
        return JsonResponse({'error': 'Host not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@organizer_required
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
        hosts = PanelHost.objects.all().order_by('name')

        # Determine selected hosts if panel_id is provided
        selected_host_ids = []
        if panel_id:
            try:
                panel = Panel.objects.get(pk=panel_id)
                selected_host_ids = list(panel.host.values_list('id', flat=True))
            except Panel.DoesNotExist:
                pass # Panel not found, no hosts are pre-selected

        hosts_data = []
        concat_avatars = build_avatar_map(hosts)
        for host in hosts:
            hosts_data.append({
                'id': host.pk,
                'name': host.name,
                'concat_user_id': host.concat_user_id,
                'profile_picture': resolve_profile_picture(host, concat_avatars),
                'selected': host.id in selected_host_ids
            })

        return JsonResponse({'hosts': hosts_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@organizer_required
@require_GET
def get_admin_hosts_ajax(request, convention_pk):
    """Return all panel hosts with panel counts scoped to the convention."""
    convention = get_object_or_404(Convention, pk=convention_pk)
    hosts = (
        PanelHost.objects.annotate(
            panels_count=Count(
                'panels',
                filter=Q(panels__convention_day__convention=convention),
                distinct=True,
            )
        )
        .order_by('name')
    )
    return JsonResponse({
        'success': True,
        'hosts': [
            {
                'id': host.pk,
                'name': host.name,
                'panels_count': host.panels_count,
            }
            for host in hosts
        ],
    })


@require_GET
def get_hosts_batch_ajax(request):
    """
    AJAX view to get details for multiple PanelHosts by IDs (comma-separated in ?ids=).
    Returns: { hosts: [ {id, name, profile_picture, panels, panels_count}, ... ] }
    """
    ids_param = request.GET.get('ids', '')
    convention_id = request.GET.get('convention_id')
    try:
        ids = [int(i) for i in ids_param.split(',') if i.strip().isdigit()]
        hosts = PanelHost.objects.filter(pk__in=ids)
        concat_avatars = build_avatar_map(hosts)
        hosts_data = []
        for host in hosts:
            panels = _get_host_panels_queryset(host, convention_id)
            panels_data = [_serialize_host_panel(panel) for panel in panels]
            panels_data.sort(key=lambda x: (x['_sort_date'], x['_sort_time']))
            for p in panels_data:
                p.pop('_sort_date', None)
                p.pop('_sort_time', None)
            hosts_data.append({
                **serialize_panel_host(host, concat_avatars),
                'panels': panels_data,
                'panels_count': len(panels_data),
            })
        return JsonResponse({'hosts': hosts_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
