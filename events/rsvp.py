from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

from .models import PanelRSVP

_rsvp_feed_signer = TimestampSigner(salt='furconnect-rsvp-feed')
RSVP_FEED_TOKEN_MAX_AGE = 60 * 60 * 24 * 365


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


def make_rsvp_feed_token(user_id):
    return _rsvp_feed_signer.sign(str(user_id))


def user_id_from_rsvp_feed_token(token):
    try:
        return _rsvp_feed_signer.unsign(token, max_age=RSVP_FEED_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def get_rsvp_attendee_ids_for_request(request, rsvp_param=None):
    user_id = None
    if rsvp_param and rsvp_param != '1':
        user_id = user_id_from_rsvp_feed_token(rsvp_param)
    if not user_id:
        user_id = request.session.get('concat_user_id')
    if not user_id:
        return None
    return _attendee_id_lookup(user_id)


def filter_panels_for_user_rsvp(panels_qs, request, rsvp_param=None):
    attendee_ids = get_rsvp_attendee_ids_for_request(request, rsvp_param)
    if not attendee_ids:
        return panels_qs.none()
    panel_ids = PanelRSVP.objects.filter(
        attendee_id__in=attendee_ids,
        panel__in=panels_qs,
    ).values_list('panel_id', flat=True).distinct()
    return panels_qs.filter(pk__in=panel_ids)


def get_user_rsvp_panel_ids(request, convention):
    user_id = request.session.get('concat_user_id')
    if not user_id:
        return set()
    return set(
        PanelRSVP.objects.filter(
            attendee_id__in=_attendee_id_lookup(user_id),
            panel__convention_day__convention=convention,
        ).values_list('panel_id', flat=True)
    )


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
