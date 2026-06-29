from django.conf import settings

from ..eventzilla import get_eventzilla_account
from ..models import PanelRSVP
from .enabled import can_rsvp, can_rsvp_with_concat, can_rsvp_with_eventzilla, is_rsvp_enabled
from .feed import get_rsvp_login_url
from .identity import get_attendee_identity, get_rsvp_attendee_ids
from .queries import get_rsvp_attendees


def get_rsvp_context(request, panel):
    if not is_rsvp_enabled():
        return {'rsvp_enabled': False, 'concat_enabled': False}

    attendee_id, display_name, avatar_url = get_attendee_identity(request)
    authenticated = bool(attendee_id)
    provider = ''
    eventzilla_account = get_eventzilla_account(request)
    if request.session.get('concat_user_id'):
        provider = 'concat'
    elif request.session.get('eventzilla_email'):
        provider = 'eventzilla'

    return {
        'rsvp_enabled': True,
        'rsvp_authenticated': authenticated,
        'rsvp_user_name': display_name,
        'rsvp_can_rsvp': can_rsvp(request),
        'rsvp_provider': provider,
        'rsvp_login_url': get_rsvp_login_url(request),
        'concat_enabled': settings.CONCAT_ENABLED,
        'concat_authenticated': bool(request.session.get('concat_user_id')),
        'concat_user_id': request.session.get('concat_user_id', ''),
        'concat_user_name': request.session.get('concat_user_name', ''),
        'concat_user_avatar': request.session.get('concat_user_avatar', ''),
        'concat_can_rsvp': can_rsvp_with_concat(request),
        'concat_role_names': request.session.get('concat_role_names', []),
        'eventzilla_enabled': settings.EVENTZILLA_ENABLED,
        'eventzilla_authenticated': bool(eventzilla_account or request.session.get('eventzilla_email')),
        'eventzilla_user_name': (
            eventzilla_account.display_name
            if eventzilla_account
            else request.session.get('eventzilla_user_name', '')
        ),
        'eventzilla_user_avatar': (
            eventzilla_account.get_avatar_display()
            if eventzilla_account
            else request.session.get('eventzilla_user_avatar', '')
        ),
        'eventzilla_can_rsvp': can_rsvp_with_eventzilla(request),
        'user_has_rsvped': (
            PanelRSVP.objects.filter(
                panel=panel,
                attendee_id__in=(get_rsvp_attendee_ids(request) or []),
            ).exists()
            if attendee_id else False
        ),
        'rsvp_count': panel.rsvps.count(),
        'rsvp_attendees': get_rsvp_attendees(panel),
    }
