from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache

from .auth import can_manage_events
from .eventzilla import get_eventzilla_account
from .rsvp import (
    can_rsvp,
    can_rsvp_with_concat,
    can_rsvp_with_eventzilla,
    get_rsvp_login_url,
    get_rsvp_user_id,
    is_rsvp_enabled,
)

_USERS_EXIST_CACHE_KEY = 'furconnect:users_exist'
_USERS_EXIST_TTL = 60 * 5


def user_exists_processor(request):
    users_exist = cache.get(_USERS_EXIST_CACHE_KEY)
    if users_exist is None:
        User = get_user_model()
        users_exist = User.objects.exists()
        cache.set(_USERS_EXIST_CACHE_KEY, users_exist, _USERS_EXIST_TTL)
    return {'users_exist': users_exist}


def concat_processor(request):
    session = request.session
    eventzilla_user_name = session.get('eventzilla_user_name', '')
    eventzilla_user_avatar = session.get('eventzilla_user_avatar', '')
    if not eventzilla_user_name and (
        session.get('eventzilla_account_id') or session.get('eventzilla_email')
    ):
        eventzilla_account = get_eventzilla_account(request)
        if eventzilla_account:
            eventzilla_user_name = eventzilla_account.display_name
            eventzilla_user_avatar = eventzilla_account.get_avatar_display()
    rsvp_user_name = session.get('concat_user_name') or eventzilla_user_name
    return {
        'concat_enabled': settings.CONCAT_ENABLED,
        'concat_authenticated': bool(session.get('concat_user_id')),
        'concat_user_id': session.get('concat_user_id', ''),
        'concat_user_name': session.get('concat_user_name', ''),
        'concat_user_avatar': session.get('concat_user_avatar', ''),
        'concat_can_rsvp': can_rsvp_with_concat(request),
        'concat_role_names': session.get('concat_role_names', []),
        'concat_is_admin': bool(session.get('concat_can_manage')),
        'eventzilla_is_admin': bool(session.get('eventzilla_can_manage')),
        'can_manage_events': can_manage_events(request),
        'eventzilla_enabled': settings.EVENTZILLA_ENABLED,
        'eventzilla_authenticated': bool(session.get('eventzilla_account_id') or session.get('eventzilla_email')),
        'eventzilla_user_name': eventzilla_user_name,
        'eventzilla_user_avatar': eventzilla_user_avatar,
        'eventzilla_can_rsvp': can_rsvp_with_eventzilla(request),
        'rsvp_enabled': is_rsvp_enabled(),
        'rsvp_authenticated': bool(get_rsvp_user_id(request)),
        'rsvp_user_name': rsvp_user_name,
        'rsvp_can_rsvp': can_rsvp(request),
        'rsvp_login_url': get_rsvp_login_url(request),
    }
