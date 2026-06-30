def normalize_email(email):
    return (email or '').strip().lower()


def normalize_barcode(barcode):
    return str(barcode or '').strip()


def attendee_barcode(attendee):
    return normalize_barcode(
        attendee.get('refno')
    )
