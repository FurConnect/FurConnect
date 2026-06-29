from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from ..auth import organizer_required
from ..models import Convention, Room

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
