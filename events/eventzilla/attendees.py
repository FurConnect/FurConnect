from .api import ensure_integration_configured, iter_attendee_pages
from .eligibility import (
    attendee_is_eligible,
    attendee_matches_barcode,
    attendee_matches_email,
    is_confirmed_attendee,
    ticket_allowed,
)
from .normalize import attendee_barcode, normalize_barcode, normalize_email


def iter_attendees_for_email(email):
    for attendee in iter_attendee_pages(email=email):
        if attendee_matches_email(attendee, email):
            yield attendee


def lookup_attendee_by_email_and_barcode(email, barcode):
    """Return the Eventzilla attendee matching email and ticket barcode."""
    ensure_integration_configured()

    email = normalize_email(email)
    barcode = normalize_barcode(barcode)
    if not email or not barcode:
        return None

    for attendee in iter_attendee_pages(email=email):
        if attendee_is_eligible(attendee, email, barcode):
            return attendee

    return None


def lookup_failure_reason(email, barcode):
    email = normalize_email(email)
    barcode = normalize_barcode(barcode)
    matches = list(iter_attendees_for_email(email))
    if not matches:
        return 'No registration found for that email address.'

    barcode_matches = [
        attendee for attendee in matches
        if attendee_matches_barcode(attendee, barcode)
    ]
    if not barcode_matches:
        return 'Email found, but the ticket barcode does not match.'

    for attendee in barcode_matches:
        if not is_confirmed_attendee(attendee):
            return 'Registration found but payment is not confirmed yet.'
        if not ticket_allowed(attendee):
            return 'This ticket type is not eligible for sign-in.'
    return 'No registration matched that email and ticket barcode.'


def parse_attendee_profile(attendee):
    first = (attendee.get('first_name') or attendee.get('buyer_first_name') or '').strip()
    last = (attendee.get('last_name') or attendee.get('buyer_last_name') or '').strip()
    email = normalize_email(attendee.get('email'))
    display_name = ' '.join(part for part in (first, last) if part).strip() or email
    attendee_id = str(attendee.get('id') or attendee.get('user_id') or email)
    return {
        'email': email,
        'display_name': display_name,
        'attendee_id': attendee_id,
        'ticket_type': attendee.get('ticket_type') or '',
        'barcode': attendee_barcode(attendee),
    }
