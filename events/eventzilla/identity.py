from .normalize import normalize_email


def attendee_id_values(email):
    normalized = normalize_email(email)
    if not normalized:
        return []
    return [normalized, f'eventzilla:{normalized}']
