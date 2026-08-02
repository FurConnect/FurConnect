from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from ..auth import organizer_required
from ..models import Convention, Room


def _next_room_sort_order(convention):
    current_max = (
        Room.objects.filter(convention=convention)
        .aggregate(Max('sort_order'))
        .get('sort_order__max')
    )
    return 0 if current_max is None else current_max + 1


@organizer_required
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


@organizer_required
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
                # Create new room at the end of the grid order
                room = Room.objects.create(
                    name=name,
                    convention=convention,
                    sort_order=_next_room_sort_order(convention),
                )

            return JsonResponse({
                'success': True,
                'room': {
                    'id': room.pk,
                    'name': room.name,
                    'sort_order': room.sort_order,
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


@organizer_required
def reorder_rooms_ajax(request, convention_pk):
    """
    AJAX view to reorder rooms for a convention.
    Expects a POST with room_ids[] in the desired display order.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

    convention = get_object_or_404(Convention, pk=convention_pk)
    room_ids = request.POST.getlist('room_ids[]')
    if not room_ids:
        return JsonResponse({'success': False, 'error': 'No room IDs provided.'}, status=400)

    try:
        rooms = {
            str(room.pk): room
            for room in Room.objects.filter(convention=convention, pk__in=room_ids)
        }
        if len(rooms) != len(room_ids):
            return JsonResponse({
                'success': False,
                'error': 'One or more rooms were not found for this convention.',
            }, status=400)

        for index, room_id in enumerate(room_ids):
            room = rooms[str(room_id)]
            if room.sort_order != index:
                room.sort_order = index
                room.save(update_fields=['sort_order'])

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def get_room_details_ajax(request, pk):
    """
    AJAX view to get details of a single Room.
    """
    try:
        room = Room.objects.get(pk=pk)
        return JsonResponse({
            'id': room.pk,
            'name': room.name,
            'sort_order': room.sort_order,
        })
    except Room.DoesNotExist:
        return JsonResponse({'error': 'Room not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@organizer_required
def get_all_rooms_ajax(request):
    """
    AJAX view to get all Rooms for a given convention.
    Requires convention_id as a GET parameter.
    """
    convention_id = request.GET.get('convention_id')

    if not convention_id:
        return JsonResponse({'error': 'convention_id is required.'}, status=400)

    try:
        rooms = Room.objects.filter(convention__id=convention_id).order_by('sort_order', 'name')
        rooms_data = []
        for room in rooms:
            rooms_data.append({
                'id': room.pk,
                'name': room.name,
                'sort_order': room.sort_order,
            })
        return JsonResponse({'rooms': rooms_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
