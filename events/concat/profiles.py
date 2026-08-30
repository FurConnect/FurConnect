import requests
from django.conf import settings
from django.core.cache import cache

from .exceptions import ConcatError
from .oauth import get_service_token
from .users import get_user_by_id

_AVATAR_CACHE_PREFIX = 'concat:avatar:'
_AVATAR_CACHE_TTL = 60 * 60 * 24
_AVATAR_MISS_TTL = 60 * 10


def extract_user_payload(response):
    if not isinstance(response, dict):
        return {}
    data = response.get('data')
    if isinstance(data, dict):
        return data
    return response


def parse_concat_user_roles(user_data):
    roles = user_data.get('userRoles') or []
    if not isinstance(roles, list):
        return set()
    return {
        role.get('name')
        for role in roles
        if isinstance(role, dict) and role.get('name')
    }


def parse_concat_user_profile(user_data):
    user_data = extract_user_payload(user_data)
    user_id = str(user_data.get('id') or user_data.get('sub') or '')
    display_name = (
        user_data.get('preferredName')
        or user_data.get('username')
        or ' '.join(
            part for part in (user_data.get('firstName'), user_data.get('lastName')) if part
        ).strip()
        or user_id
    )
    avatar_url = (
        user_data.get('profilePictureUrl')
        or user_data.get('profilePictureURL')
        or user_data.get('avatarUrl')
        or ''
    )
    return {
        'user_id': user_id,
        'display_name': display_name,
        'avatar_url': avatar_url,
    }


def parse_concat_user(user_data):
    user_data = extract_user_payload(user_data)
    profile = parse_concat_user_profile(user_data)
    return {
        **profile,
        'avatar_url': user_data.get('profilePictureUrl') or profile['avatar_url'],
        'role_names': sorted(parse_concat_user_roles(user_data)),
    }


def get_concat_profile_picture_url(user_id, token=None):
    if not settings.CONCAT_ENABLED or not user_id:
        return ''
    cache_key = f'{_AVATAR_CACHE_PREFIX}{user_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        profile = parse_concat_user_profile(get_user_by_id(user_id, token=token))
        avatar_url = profile.get('avatar_url') or ''
    except (ConcatError, requests.RequestException):
        avatar_url = ''
    cache.set(cache_key, avatar_url, timeout=_AVATAR_CACHE_TTL if avatar_url else _AVATAR_MISS_TTL)
    return avatar_url


def get_concat_profile_pictures(user_ids, token=None):
    user_ids = [str(user_id).strip() for user_id in user_ids if user_id and str(user_id).strip()]
    if not user_ids or not settings.CONCAT_ENABLED:
        return {}

    unique_ids = list(dict.fromkeys(user_ids))
    pictures = {}
    missing_ids = []
    for user_id in unique_ids:
        cached = cache.get(f'{_AVATAR_CACHE_PREFIX}{user_id}')
        if cached is not None:
            pictures[user_id] = cached
        else:
            missing_ids.append(user_id)

    if not missing_ids:
        return pictures

    if token is None:
        try:
            token = get_service_token(scope='user:read')
        except (ConcatError, requests.RequestException):
            return pictures

    for user_id in missing_ids:
        pictures[user_id] = get_concat_profile_picture_url(user_id, token=token)
    return pictures
