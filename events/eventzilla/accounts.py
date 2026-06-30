from ..models import EventzillaAttendee
from .attendees import lookup_attendee_by_email_and_barcode, lookup_failure_reason, parse_attendee_profile
from .normalize import normalize_barcode, normalize_email

SESSION_KEYS = (
    'eventzilla_account_id',
    'eventzilla_email',
    'eventzilla_user_name',
    'eventzilla_user_avatar',
    'eventzilla_attendee_id',
    'eventzilla_can_rsvp',
    'eventzilla_can_manage',
    'eventzilla_is_admin',
)


def get_eventzilla_account(request):
    account_id = request.session.get('eventzilla_account_id')
    if account_id:
        account = EventzillaAttendee.objects.filter(pk=account_id).first()
        if account:
            return account

    email = request.session.get('eventzilla_email')
    if email:
        return EventzillaAttendee.objects.filter(email=normalize_email(email)).first()
    return None


def store_eventzilla_session(request, account):
    request.session['eventzilla_account_id'] = account.pk
    request.session['eventzilla_email'] = account.email
    request.session['eventzilla_user_name'] = account.display_name
    request.session['eventzilla_attendee_id'] = account.eventzilla_attendee_id
    request.session['eventzilla_user_avatar'] = account.get_avatar_display()
    request.session['eventzilla_can_rsvp'] = True
    request.session['eventzilla_can_manage'] = account.is_site_admin
    request.session['eventzilla_is_admin'] = account.is_site_admin


def clear_eventzilla_session(request):
    for key in SESSION_KEYS:
        request.session.pop(key, None)


def authenticate_eventzilla_credentials(request, email, barcode):
    """Verify email + barcode against Eventzilla and create or load a local account."""
    email = normalize_email(email)
    barcode = normalize_barcode(barcode)
    if not email or not barcode:
        return None, 'Email and ticket barcode are required.', False

    attendee = lookup_attendee_by_email_and_barcode(email, barcode)
    if not attendee:
        return None, lookup_failure_reason(email, barcode), False

    profile = parse_attendee_profile(attendee)
    account, created = EventzillaAttendee.objects.get_or_create(
        email=email,
        defaults={
            'barcode': profile['barcode'],
            'display_name': profile['display_name'],
            'eventzilla_attendee_id': profile['attendee_id'],
        },
    )
    if not created:
        if account.barcode and account.barcode != profile['barcode']:
            return None, 'That ticket barcode does not match this registration.', False
        update_fields = []
        if not account.barcode:
            account.barcode = profile['barcode']
            update_fields.append('barcode')
        if profile['attendee_id'] and account.eventzilla_attendee_id != profile['attendee_id']:
            account.eventzilla_attendee_id = profile['attendee_id']
            update_fields.append('eventzilla_attendee_id')
        if not account.display_name and profile['display_name']:
            account.display_name = profile['display_name']
            update_fields.append('display_name')
        if update_fields:
            account.save(update_fields=update_fields)

    store_eventzilla_session(request, account)
    return account, None, created


def update_eventzilla_profile(account, *, display_name=None, avatar=None):
    update_fields = []
    if display_name is not None:
        cleaned_name = display_name.strip()
        if cleaned_name:
            account.display_name = cleaned_name
            update_fields.append('display_name')
    if avatar is not None:
        account.avatar = avatar
        update_fields.append('avatar')
    if update_fields:
        account.save(update_fields=update_fields + ['updated_at'])
    return account
