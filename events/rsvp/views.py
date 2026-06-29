from urllib.parse import quote

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ..models import Panel, PanelRSVP
from .enabled import can_rsvp
from .feed import get_rsvp_login_url
from .identity import get_attendee_identity, get_rsvp_attendee_ids
from .queries import get_rsvp_attendees


@require_POST
def panel_rsvp_toggle(request, pk):
    if not settings.CONCAT_ENABLED and not settings.EVENTZILLA_ENABLED:
        return JsonResponse({'error': 'RSVP is not enabled.'}, status=400)

    panel = get_object_or_404(Panel, pk=pk)

    if panel.cancelled:
        return JsonResponse({'error': 'This event has been cancelled.'}, status=400)

    attendee_id, display_name, avatar_url = get_attendee_identity(request)
    if not attendee_id:
        if request.session.get('concat_user_id') and not can_rsvp(request):
            return JsonResponse({
                'error': 'Your account is not eligible to RSVP to panels.',
                'requires_role': True,
            }, status=403)
        login_url = get_rsvp_login_url(request)
        return JsonResponse({
            'error': 'Sign in to RSVP.',
            'requires_login': True,
            'requires_concat': settings.CONCAT_ENABLED,
            'requires_eventzilla': (
                settings.EVENTZILLA_ENABLED and not settings.CONCAT_ENABLED
            ),
            'concat_login_url': login_url,
            'login_url': login_url,
        }, status=401)

    attendee_ids = get_rsvp_attendee_ids(request) or []
    existing = PanelRSVP.objects.filter(
        panel=panel,
        attendee_id__in=attendee_ids,
    ).first()
    if existing:
        existing.delete()
        return JsonResponse({
            'rsvped': False,
            'rsvp_count': panel.rsvps.count(),
            'rsvp_attendees': get_rsvp_attendees(panel),
        })

    PanelRSVP.objects.create(
        panel=panel,
        attendee_id=attendee_id,
        display_name=display_name,
        avatar_url=avatar_url,
    )
    return JsonResponse({
        'rsvped': True,
        'rsvp_count': panel.rsvps.count(),
        'rsvp_attendees': get_rsvp_attendees(panel),
    })
