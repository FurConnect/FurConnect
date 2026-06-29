from ..eventzilla import attendee_id_values, get_eventzilla_account


def concat_attendee_id_values(user_id):
    if not user_id:
        return []
    return [user_id, f'concat:{user_id}']


def get_rsvp_attendee_ids(request):
    concat_user_id = request.session.get('concat_user_id')
    if concat_user_id:
        return concat_attendee_id_values(concat_user_id)
    eventzilla_email = request.session.get('eventzilla_email')
    if eventzilla_email:
        return attendee_id_values(eventzilla_email)
    return None


def get_rsvp_user_id(request):
    return request.session.get('concat_user_id') or request.session.get('eventzilla_email')


def get_concat_attendee_identity(request):
    user_id = request.session.get('concat_user_id')
    if not user_id:
        return None, None, ''
    display_name = request.session.get('concat_user_name', '')
    avatar_url = request.session.get('concat_user_avatar', '')
    return user_id, display_name, avatar_url


def get_eventzilla_attendee_identity(request):
    account = get_eventzilla_account(request)
    if not account:
        email = request.session.get('eventzilla_email')
        if not email:
            return None, None, ''
        display_name = request.session.get('eventzilla_user_name', email)
        avatar = request.session.get('eventzilla_user_avatar', '')
        return email, display_name, avatar
    return account.email, account.display_name, account.get_avatar_display()


def get_attendee_identity(request):
    identity = get_concat_attendee_identity(request)
    if identity[0]:
        return identity
    return get_eventzilla_attendee_identity(request)
