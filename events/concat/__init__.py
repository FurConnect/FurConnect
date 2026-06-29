"""ConCat OAuth integration, user profiles, and access control."""

from .access import resolve_concat_access
from .exceptions import ConcatError
from .hosts import apply_host_profile_image, attach_host_avatar_urls, build_avatar_map, resolve_profile_picture, serialize_panel_host
from .oauth import exchange_code_for_token, get_authorize_url, get_service_token
from .profiles import (
    get_concat_profile_picture_url,
    get_concat_profile_pictures,
    parse_concat_user,
    parse_concat_user_profile,
)
from .registration import get_registration
from .users import get_user, get_user_by_id, get_user_role_names, user_has_any_role

__all__ = [
    'ConcatError',
    'apply_host_profile_image',
    'attach_host_avatar_urls',
    'build_avatar_map',
    'exchange_code_for_token',
    'get_authorize_url',
    'get_concat_profile_picture_url',
    'get_concat_profile_pictures',
    'get_registration',
    'get_service_token',
    'get_user',
    'get_user_by_id',
    'get_user_role_names',
    'parse_concat_user',
    'parse_concat_user_profile',
    'resolve_concat_access',
    'resolve_profile_picture',
    'serialize_panel_host',
    'user_has_any_role',
]
