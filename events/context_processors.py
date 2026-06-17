from django.contrib.auth import get_user_model
from django.conf import settings

from .auth import can_manage_events


def user_exists_processor(request):
    User = get_user_model()
    users_exist = User.objects.exists()
    return {'users_exist': users_exist}


def concat_processor(request):
    return {
        'concat_enabled': settings.CONCAT_ENABLED,
        'concat_authenticated': bool(request.session.get('concat_user_id')),
        'concat_user_id': request.session.get('concat_user_id', ''),
        'concat_user_name': request.session.get('concat_user_name', ''),
        'concat_user_avatar': request.session.get('concat_user_avatar', ''),
        'concat_can_rsvp': bool(request.session.get('concat_can_rsvp')),
        'concat_role_names': request.session.get('concat_role_names', []),
        'concat_is_admin': bool(request.session.get('concat_can_manage')),
        'can_manage_events': can_manage_events(request),
    } 