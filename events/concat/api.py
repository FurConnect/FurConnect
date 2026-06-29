import threading

import requests
from django.conf import settings

from .exceptions import ConcatError

_session_local = threading.local()


def get_session():
    session = getattr(_session_local, 'session', None)
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': 'FurConnect/1.0'})
        _session_local.session = session
    return session


def csrf_token(session):
    return (
        session.cookies.get('csrftoken')
        or session.cookies.get('_csrf')
        or session.cookies.get('XSRF-TOKEN')
    )


def api_headers(*, csrf_token_value=None, bearer=None):
    headers = {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': settings.CONCAT_API_BASE,
    }
    if csrf_token_value:
        headers['X-CSRF-Token'] = csrf_token_value
    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    return headers


def parse_response(response):
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


def prime_csrf(session):
    session.get(settings.CONCAT_API_BASE, timeout=15)


def post_token(payload):
    session = get_session()
    prime_csrf(session)
    headers = api_headers(csrf_token_value=csrf_token(session))
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
    return parse_response(response)


def get_json(url, *, bearer=None):
    session = get_session()
    response = session.get(
        url,
        headers=api_headers(bearer=bearer),
        timeout=15,
    )
    return parse_response(response)
