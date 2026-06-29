import threading

import requests
from django.conf import settings

from .exceptions import EventzillaError

_session_local = threading.local()
ATTENDEE_PAGE_SIZE = 100


def get_session():
    session = getattr(_session_local, 'session', None)
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': 'FurConnect/1.0'})
        _session_local.session = session
    return session


def api_headers():
    return {
        'Accept': 'application/json',
        'x-api-key': settings.EVENTZILLA_API_KEY,
    }


def parse_response(response):
    if not response.ok:
        raise EventzillaError(
            f'Eventzilla API error ({response.status_code}): {response.text[:512]}'
        )

    if not response.text:
        return {}

    try:
        return response.json()
    except ValueError as exc:
        raise EventzillaError(
            f'Invalid JSON from Eventzilla API: {response.text[:256]}'
        ) from exc


def get_json(path, *, params=None):
    base = settings.EVENTZILLA_API_BASE.rstrip('/')
    url = f'{base}/{path.lstrip("/")}'
    response = get_session().get(
        url,
        headers=api_headers(),
        params=params,
        timeout=15,
    )
    return parse_response(response)


def pagination_total(data):
    pagination = data.get('pagination')
    if isinstance(pagination, list) and pagination:
        return pagination[0].get('total')
    if isinstance(pagination, dict):
        return pagination.get('total')
    return None


def attendees_path():
    return f'events/{settings.EVENTZILLA_EVENT_ID}/attendees'


def iter_attendee_pages(*, email=None):
    """Yield attendee records from Eventzilla, paginating when needed."""
    path = attendees_path()

    if email:
        try:
            data = get_json(path, params={'email': email})
            yield from data.get('attendees') or []
        except EventzillaError:
            pass

    offset = 0
    while True:
        data = get_json(path, params={'offset': offset, 'limit': ATTENDEE_PAGE_SIZE})
        attendees = data.get('attendees') or []
        if not attendees:
            break

        yield from attendees

        total = pagination_total(data)
        offset += len(attendees)
        if total is not None and offset >= total:
            break
        if len(attendees) < ATTENDEE_PAGE_SIZE:
            break


def ensure_integration_configured():
    if not settings.EVENTZILLA_ENABLED:
        raise EventzillaError('Eventzilla integration is not enabled.')
    if not settings.EVENTZILLA_API_KEY:
        raise EventzillaError('EVENTZILLA_API_KEY is not configured.')
    if not settings.EVENTZILLA_EVENT_ID:
        raise EventzillaError('EVENTZILLA_EVENT_ID is not configured.')
