from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.urls import reverse
from urllib.parse import quote

from django.conf import settings

from .identity import concat_attendee_id_values, get_rsvp_user_id

_rsvp_feed_signer = TimestampSigner(salt='furconnect-rsvp-feed')
RSVP_FEED_TOKEN_MAX_AGE = 60 * 60 * 24 * 365


def get_rsvp_login_url(request):
    next_url = quote(request.get_full_path() if hasattr(request, 'get_full_path') else '/')
    if settings.CONCAT_ENABLED:
        return f"{reverse('events:concat_login')}?next={next_url}"
    if settings.EVENTZILLA_ENABLED:
        return f"{reverse('events:eventzilla_login')}?next={next_url}"
    return reverse('events:login')


def make_rsvp_feed_token(user_id):
    return _rsvp_feed_signer.sign(str(user_id))


def user_id_from_rsvp_feed_token(token):
    try:
        return _rsvp_feed_signer.unsign(token, max_age=RSVP_FEED_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def get_rsvp_attendee_ids_for_request(request, rsvp_param=None):
    from ..eventzilla import attendee_id_values

    user_id = None
    if rsvp_param and rsvp_param != '1':
        user_id = user_id_from_rsvp_feed_token(rsvp_param)
    if not user_id:
        user_id = get_rsvp_user_id(request)
    if not user_id:
        return None

    if request.session.get('concat_user_id') == user_id:
        return concat_attendee_id_values(user_id)
    if request.session.get('eventzilla_email') == user_id:
        return attendee_id_values(user_id)

    if ':' not in str(user_id):
        return concat_attendee_id_values(user_id)
    return [user_id]
