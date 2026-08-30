from urllib.parse import quote, unquote

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner, dumps, loads
from django.urls import reverse

from .identity import concat_attendee_id_values, get_rsvp_user_id

RSVP_FEED_SALT = 'furconnect-rsvp-feed'
_rsvp_feed_signer = TimestampSigner(salt=RSVP_FEED_SALT)
RSVP_FEED_TOKEN_MAX_AGE = 60 * 60 * 24 * 365


def get_rsvp_login_url(request):
    next_url = quote(request.get_full_path() if hasattr(request, 'get_full_path') else '/')
    if settings.CONCAT_ENABLED:
        return f"{reverse('events:concat_login')}?next={next_url}"
    if settings.EVENTZILLA_ENABLED:
        return f"{reverse('events:eventzilla_login')}?next={next_url}"
    return reverse('events:login')


def make_rsvp_feed_token(user_id):
    """URL-safe token for calendar clients (no colons, @, or raw user id)."""
    packed = dumps(str(user_id), salt=RSVP_FEED_SALT)
    return packed.replace(':', '.')


def user_id_from_rsvp_feed_token(token):
    if not token:
        return None
    token = unquote(str(token).strip())
    if token in {'1', 'true', 'yes'}:
        return None

    candidates = [token]
    if '.' in token and ':' not in token:
        candidates.append(token.replace('.', ':'))

    for candidate in candidates:
        try:
            return str(loads(candidate, salt=RSVP_FEED_SALT, max_age=RSVP_FEED_TOKEN_MAX_AGE))
        except (BadSignature, SignatureExpired, TypeError, ValueError):
            pass
        try:
            return str(_rsvp_feed_signer.unsign(candidate, max_age=RSVP_FEED_TOKEN_MAX_AGE))
        except (BadSignature, SignatureExpired, TypeError, ValueError):
            pass
    return None


def attendee_ids_for_feed_user(user_id):
    from ..eventzilla import attendee_id_values

    if not user_id:
        return None
    user_id = str(user_id)
    ids = []
    if '@' in user_id:
        ids.extend(attendee_id_values(user_id))
    ids.extend(concat_attendee_id_values(user_id))
    return list(dict.fromkeys(ids)) or None


def get_rsvp_attendee_ids_for_request(request, rsvp_param=None):
    user_id = None
    if rsvp_param and rsvp_param != '1':
        user_id = user_id_from_rsvp_feed_token(rsvp_param)
    if not user_id:
        user_id = get_rsvp_user_id(request)
    if not user_id:
        return None
    return attendee_ids_for_feed_user(user_id)
