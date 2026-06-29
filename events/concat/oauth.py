import requests
from django.conf import settings

from .api import post_token
from .exceptions import ConcatError


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
    return post_token({
        'client_id': settings.CONCAT_CLIENT_ID,
        'client_secret': settings.CONCAT_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': settings.CONCAT_REDIRECT_URI,
        'scope': 'pii:basic',
    })


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
            data = post_token({
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
