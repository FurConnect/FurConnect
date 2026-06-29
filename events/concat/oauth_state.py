from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils.crypto import get_random_string

from ..navigation import sanitize_next_url

_oauth_signer = TimestampSigner(salt='furconnect-concat-oauth')


def pack_oauth_state(next_url):
    payload = f'{get_random_string(32)}|{sanitize_next_url(next_url)}'
    return _oauth_signer.sign(payload)


def unpack_oauth_state(signed_state):
    try:
        payload = _oauth_signer.unsign(signed_state, max_age=600)
    except (BadSignature, SignatureExpired):
        return None
    if '|' not in payload:
        return None
    _, next_url = payload.split('|', 1)
    return sanitize_next_url(next_url)
