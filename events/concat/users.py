from django.conf import settings

from .api import get_json
from .oauth import get_service_token


def get_user(token):
    return get_json(f'{settings.CONCAT_API_BASE}/api/users/current', bearer=token)


def get_user_by_id(user_id, token=None):
    if token is None:
        token = get_service_token(scope='user:read')
    return get_json(f'{settings.CONCAT_API_V0_BASE}/users/{user_id}', bearer=token)


def get_user_roles(user_id, token=None):
    if token is None:
        token = get_service_token()
    return get_json(f'{settings.CONCAT_API_V0_BASE}/users/{user_id}/roles', bearer=token)


def get_user_role_names(user_id, token=None):
    roles_response = get_user_roles(user_id, token=token)
    roles = roles_response.get('data') or []
    return {role.get('name') for role in roles if role.get('name')}


def user_has_any_role(user_id, role_names, token=None):
    if not role_names:
        return False
    return bool(get_user_role_names(user_id, token=token) & set(role_names))
