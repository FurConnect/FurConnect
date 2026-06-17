import threading

import requests
from django.conf import settings


class ConcatError(Exception):
    pass


_session_local = threading.local()


def _get_session():
    session = getattr(_session_local, 'session', None)
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': 'FurConnect/1.0'})
        _session_local.session = session
    return session


def _csrf_token(session):
    return (
        session.cookies.get('csrftoken')
        or session.cookies.get('_csrf')
        or session.cookies.get('XSRF-TOKEN')
    )


def _api_headers(*, csrf_token=None, bearer=None):
    headers = {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': settings.CONCAT_API_BASE,
    }
    if csrf_token:
        headers['X-CSRF-Token'] = csrf_token
    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    return headers


def _parse_response(response):
    if not response.ok:
        raise ConcatError(
            f'Concat API error ({response.status_code}): {response.text[:512]}'
        )

    if not response.text:
        return {}

    content_type = response.headers.get('Content-Type', '')
    if 'application/json' not in content_type and response.text.lstrip().startswith('<!'):
        raise ConcatError(
            'Concat API returned HTML instead of JSON. '
            'Check CONCAT_TOKEN_ENDPOINT (should be /api/oauth/token).'
        )

    try:
        return response.json()
    except ValueError as exc:
        raise ConcatError(f'Invalid JSON from Concat API: {response.text[:256]}') from exc


def _prime_csrf(session):
    session.get(settings.CONCAT_API_BASE, timeout=15)


def _post_token(payload):
    session = _get_session()
    _prime_csrf(session)
    headers = _api_headers(csrf_token=_csrf_token(session))
    headers['Content-Type'] = 'application/x-www-form-urlencoded'

    response = session.post(
        settings.CONCAT_TOKEN_ENDPOINT,
        data=payload,
        headers=headers,
        timeout=15,
    )
    if response.status_code == 415:
        response = session.post(
            settings.CONCAT_TOKEN_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=15,
        )
    return _parse_response(response)


def _get_json(url, *, bearer=None):
    session = _get_session()
    response = session.get(
        url,
        headers=_api_headers(bearer=bearer),
        timeout=15,
    )
    return _parse_response(response)


def get_authorize_url(state):
    params = {
        'client_id': settings.CONCAT_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': settings.CONCAT_REDIRECT_URI,
        'scope': 'pii:basic',
        'state': state,
    }
    query = '&'.join(f'{key}={requests.utils.quote(str(value))}' for key, value in params.items())
    return f'{settings.CONCAT_API_BASE}/oauth/authorize?{query}'


def exchange_code_for_token(code):
    return _post_token({
        'client_id': settings.CONCAT_CLIENT_ID,
        'client_secret': settings.CONCAT_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': settings.CONCAT_REDIRECT_URI,
        'scope': 'pii:basic',
    })


def get_user(token):
    return _get_json(f'{settings.CONCAT_API_BASE}/api/users/current', bearer=token)


def get_user_by_id(user_id, token=None):
    if token is None:
        token = get_service_token(scope='user:read')
    return _get_json(f'{settings.CONCAT_API_V0_BASE}/users/{user_id}', bearer=token)


def _extract_concat_user_payload(response):
    if not isinstance(response, dict):
        return {}
    data = response.get('data')
    if isinstance(data, dict):
        return data
    return response


def parse_concat_user_profile(user_data):
    user_data = _extract_concat_user_payload(user_data)
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


def get_concat_profile_picture_url(user_id, token=None):
    if not settings.CONCAT_ENABLED or not user_id:
        return ''
    try:
        profile = parse_concat_user_profile(get_user_by_id(user_id, token=token))
        return profile.get('avatar_url') or ''
    except (ConcatError, requests.RequestException):
        return ''


def get_concat_profile_pictures(user_ids, token=None):
    user_ids = [str(user_id).strip() for user_id in user_ids if user_id and str(user_id).strip()]
    if not user_ids or not settings.CONCAT_ENABLED:
        return {}

    unique_ids = list(dict.fromkeys(user_ids))
    if token is None:
        try:
            token = get_service_token(scope='user:read')
        except (ConcatError, requests.RequestException):
            return {}

    pictures = {}
    for user_id in unique_ids:
        pictures[user_id] = get_concat_profile_picture_url(user_id, token=token)
    return pictures


def parse_concat_user_roles(user_data):
    roles = user_data.get('userRoles') or []
    if not isinstance(roles, list):
        return set()
    return {
        role.get('name')
        for role in roles
        if isinstance(role, dict) and role.get('name')
    }


def parse_concat_user(user_data):
    user_id = str(user_data.get('id') or user_data.get('sub') or '')
    display_name = (
        user_data.get('preferredName')
        or user_data.get('username')
        or ' '.join(
            part for part in (user_data.get('firstName'), user_data.get('lastName')) if part
        ).strip()
        or user_id
    )
    return {
        'user_id': user_id,
        'display_name': display_name,
        'avatar_url': user_data.get('profilePictureUrl') or '',
        'role_names': sorted(parse_concat_user_roles(user_data)),
    }


def get_service_token(scope=None):
    scopes_to_try = []
    if scope:
        scopes_to_try.append(scope)
    else:
        scopes_to_try.extend([
            settings.CONCAT_SERVICE_SCOPES,
            'user:read registration:read',
            'user:read',
            'registration:read',
        ])

    last_error = None
    seen = set()
    for scope_value in scopes_to_try:
        scope_value = (scope_value or '').strip()
        if not scope_value or scope_value in seen:
            continue
        seen.add(scope_value)
        try:
            data = _post_token({
                'client_id': settings.CONCAT_CLIENT_ID,
                'client_secret': settings.CONCAT_CLIENT_SECRET,
                'grant_type': 'client_credentials',
                'scope': scope_value,
            })
            token = data.get('access_token')
            if not token:
                raise ConcatError('Concat service token response missing access_token')
            return token
        except ConcatError as exc:
            last_error = exc

    raise last_error or ConcatError('Unable to obtain ConCat service token')


def get_user_roles(user_id, token=None):
    if token is None:
        token = get_service_token()
    return _get_json(f'{settings.CONCAT_API_V0_BASE}/users/{user_id}/roles', bearer=token)


def get_user_role_names(user_id, token=None):
    roles_response = get_user_roles(user_id, token=token)
    roles = roles_response.get('data') or []
    return {role.get('name') for role in roles if role.get('name')}


def user_has_any_role(user_id, role_names, token=None):
    if not role_names:
        return False
    return bool(get_user_role_names(user_id, token=token) & set(role_names))


def get_registration(user_id, token=None):
    if token is None:
        token = get_service_token()
    return _get_json(f'{settings.CONCAT_API_V0_BASE}/users/{user_id}/registration', bearer=token)


def _resolve_concat_role_names(user_id, *, user_data=None):
    """Prefer the service roles API; fall back to OAuth userRoles."""
    try:
        service_token = get_service_token()
        return get_user_role_names(user_id, token=service_token), service_token
    except ConcatError:
        role_names = parse_concat_user_roles(user_data) if user_data else set()
        return role_names, None


def resolve_concat_access(user_id, *, user_data=None):
    """Return role names and RSVP eligibility from ConCat roles/registration."""
    role_names, service_token = _resolve_concat_role_names(user_id, user_data=user_data)

    manage_roles = set(settings.CONCAT_MANAGE_ROLES)
    skip_roles = set(settings.CONCAT_SKIP_RSVP_ROLES)
    required_roles = set(settings.CONCAT_RSVP_REQUIRED_ROLES)
    can_manage = bool(role_names & manage_roles) if manage_roles else False
    skip_rsvp = bool(role_names & skip_roles)

    can_rsvp = True
    if required_roles:
        can_rsvp = bool(role_names & required_roles)

    if can_rsvp and settings.CONCAT_REQUIRE_PAID_REGISTRATION:
        try:
            if service_token is None:
                service_token = get_service_token()
            registration = get_registration(user_id, token=service_token)
            if registration.get('status') != 'paid':
                can_rsvp = False
            elif settings.CONCAT_RSVP_PRODUCT_IDS:
                product_id = registration.get('productId')
                allowed_ids = {int(value) for value in settings.CONCAT_RSVP_PRODUCT_IDS}
                can_rsvp = product_id in allowed_ids
        except ConcatError:
            can_rsvp = False

    return {
        'role_names': sorted(role_names),
        'can_manage': can_manage,
        'skip_rsvp': skip_rsvp,
        'can_rsvp': can_rsvp,
    }
