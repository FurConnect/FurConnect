from django.conf import settings

from .normalize import attendee_barcode, normalize_barcode, normalize_email


def attendee_matches_email(attendee, email):
    return normalize_email(attendee.get('email')) == email


def attendee_matches_barcode(attendee, barcode):
    return attendee_barcode(attendee) == normalize_barcode(barcode)


def is_confirmed_attendee(attendee):
    if not settings.EVENTZILLA_REQUIRE_PAID_REGISTRATION:
        return True
    status = (attendee.get('transaction_status') or '').strip().lower()
    return status in {'confirmed', 'complete', 'completed', 'paid', 'success'}


def ticket_allowed(attendee):
    allowed = settings.EVENTZILLA_ALLOWED_TICKET_TYPES
    if not allowed:
        return True
    ticket_type = (attendee.get('ticket_type') or '').strip()
    return ticket_type in allowed


def attendee_is_eligible(attendee, email, barcode):
    return (
        attendee_matches_email(attendee, email)
        and attendee_matches_barcode(attendee, barcode)
        and is_confirmed_attendee(attendee)
        and ticket_allowed(attendee)
    )


def find_eligible_attendee(attendees, email, barcode):
    for attendee in attendees:
        if attendee_is_eligible(attendee, email, barcode):
            return attendee
    return None
