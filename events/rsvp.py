from django.conf import settings

from .models import PanelRSVP


def can_rsvp_with_concat(request):
    if not settings.CONCAT_ENABLED:
        return False
    if not request.session.get('concat_user_id'):
        return False
    if request.session.get('concat_can_rsvp'):
        return True
    return bool(request.session.get('concat_can_manage'))


def _attendee_id_lookup(user_id):
    if not user_id:
        return []
    return [user_id, f'concat:{user_id}']


def get_concat_attendee_identity(request):
    user_id = request.session.get('concat_user_id')
    if not user_id:
        return None, None, ''
    display_name = request.session.get('concat_user_name', '')
    avatar_url = request.session.get('concat_user_avatar', '')
    return user_id, display_name, avatar_url


def get_rsvp_attendees(panel):
    return [
        {
            'display_name': rsvp.display_name or rsvp.attendee_id,
            'avatar_url': rsvp.avatar_url,
        }
        for rsvp in panel.rsvps.all()
    ]


def get_rsvp_context(request, panel):
    if not settings.CONCAT_ENABLED:
        return {'concat_enabled': False}

    user_id = request.session.get('concat_user_id')
    authenticated = bool(user_id)
    return {
        'concat_enabled': True,
        'concat_authenticated': authenticated,
        'concat_user_id': user_id or '',
        'concat_user_name': request.session.get('concat_user_name', ''),
        'concat_user_avatar': request.session.get('concat_user_avatar', ''),
        'concat_can_rsvp': can_rsvp_with_concat(request),
        'concat_role_names': request.session.get('concat_role_names', []),
        'user_has_rsvped': (
            PanelRSVP.objects.filter(
                panel=panel,
                attendee_id__in=_attendee_id_lookup(user_id),
            ).exists()
            if user_id else False
        ),
        'rsvp_count': panel.rsvps.count(),
        'rsvp_attendees': get_rsvp_attendees(panel),
    }
