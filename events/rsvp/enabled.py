from django.conf import settings


def is_rsvp_enabled():
    return settings.CONCAT_ENABLED or settings.EVENTZILLA_ENABLED


def can_rsvp_with_concat(request):
    if not settings.CONCAT_ENABLED:
        return False
    if not request.session.get('concat_user_id'):
        return False
    if request.session.get('concat_can_rsvp'):
        return True
    return bool(request.session.get('concat_can_manage'))


def can_rsvp_with_eventzilla(request):
    if not settings.EVENTZILLA_ENABLED:
        return False
    if not request.session.get('eventzilla_email'):
        return False
    if request.session.get('eventzilla_can_rsvp'):
        return True
    return bool(request.session.get('eventzilla_can_manage'))


def can_rsvp(request):
    return can_rsvp_with_concat(request) or can_rsvp_with_eventzilla(request)
