from django.conf import settings

from .exceptions import ConcatError
from .oauth import get_service_token
from .profiles import parse_concat_user_roles
from .registration import get_registration, registration_product_ids
from .users import get_user_role_names


def resolve_role_names(user_id, *, user_data=None):
    try:
        service_token = get_service_token()
        return get_user_role_names(user_id, token=service_token), service_token
    except ConcatError:
        role_names = parse_concat_user_roles(user_data) if user_data else set()
        return role_names, None


def resolve_concat_access(user_id, *, user_data=None):
    """Return role names and RSVP eligibility from ConCat roles/registration."""
    role_names, service_token = resolve_role_names(user_id, user_data=user_data)

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
                allowed_ids = {int(value) for value in settings.CONCAT_RSVP_PRODUCT_IDS}
                can_rsvp = bool(registration_product_ids(registration) & allowed_ids)
        except ConcatError:
            can_rsvp = False

    return {
        'role_names': sorted(role_names),
        'can_manage': can_manage,
        'skip_rsvp': skip_rsvp,
        'can_rsvp': can_rsvp,
    }
