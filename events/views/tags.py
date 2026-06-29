from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..auth import organizer_required
from ..forms import TagForm
from ..models import Tag

@organizer_required
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


@organizer_required
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


@organizer_required
def tag_delete(request, name):
    try:
        tag = Tag.objects.get(name__iexact=name)
    except Tag.DoesNotExist:
        messages.error(request, 'Tag not found.')
        return redirect('events:schedule')

    convention_pk = None
    first_panel = tag.panels.select_related('convention_day').first()
    if first_panel:
        convention_pk = first_panel.convention_day.convention_id

    if request.method == 'POST':
        tag.delete()
        messages.success(request, 'Tag deleted successfully!')
        if convention_pk:
            return redirect('events:admin_panel_section', pk=convention_pk, section='tags')
        return redirect('events:schedule')

    return render(request, 'events/tag_confirm_delete.html', {
        'tag': tag,
        'current_convention_name': 'FurConnect',
    })


@organizer_required
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


@organizer_required
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


@organizer_required
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
