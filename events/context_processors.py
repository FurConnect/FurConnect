from django.contrib.auth import get_user_model
from django.conf import settings

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


def user_exists_processor(request):
    User = get_user_model()
    users_exist = User.objects.exists()
    return {'users_exist': users_exist}


def concat_processor(request):
    eventzilla_account = get_eventzilla_account(request)
    eventzilla_user_name = (
        eventzilla_account.display_name
        if eventzilla_account
        else request.session.get('eventzilla_user_name', '')
    )
    eventzilla_user_avatar = (
        eventzilla_account.get_avatar_display()
        if eventzilla_account
        else request.session.get('eventzilla_user_avatar', '')
    )
    rsvp_user_name = request.session.get('concat_user_name') or eventzilla_user_name
    return {
        'concat_enabled': settings.CONCAT_ENABLED,
        'concat_authenticated': bool(request.session.get('concat_user_id')),
        'concat_user_id': request.session.get('concat_user_id', ''),
        'concat_user_name': request.session.get('concat_user_name', ''),
        'concat_user_avatar': request.session.get('concat_user_avatar', ''),
        'concat_can_rsvp': can_rsvp_with_concat(request),
        'concat_role_names': request.session.get('concat_role_names', []),
        'concat_is_admin': bool(request.session.get('concat_can_manage')),
        'eventzilla_is_admin': bool(request.session.get('eventzilla_can_manage')),
        'can_manage_events': can_manage_events(request),
        'eventzilla_enabled': settings.EVENTZILLA_ENABLED,
        'eventzilla_authenticated': bool(eventzilla_account or request.session.get('eventzilla_email')),
        'eventzilla_user_name': eventzilla_user_name,
        'eventzilla_user_avatar': eventzilla_user_avatar,
        'eventzilla_can_rsvp': can_rsvp_with_eventzilla(request),
        'rsvp_enabled': is_rsvp_enabled(),
        'rsvp_authenticated': bool(get_rsvp_user_id(request)),
        'rsvp_user_name': rsvp_user_name,
        'rsvp_can_rsvp': can_rsvp(request),
        'rsvp_login_url': get_rsvp_login_url(request),
    }
