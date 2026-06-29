SESSION_KEYS = (
    'concat_user_id',
    'concat_user_name',
    'concat_user_avatar',
    'concat_role_names',
    'concat_skip_rsvp',
    'concat_can_manage',
    'concat_can_rsvp',
    'concat_is_admin',
)


def store_concat_session(request, profile, access):
    request.session['concat_user_id'] = profile['user_id']
    request.session['concat_user_name'] = profile['display_name']
    request.session['concat_user_avatar'] = profile['avatar_url']
    request.session['concat_role_names'] = access.get('role_names', profile.get('role_names', []))
    request.session['concat_skip_rsvp'] = access.get('skip_rsvp', False)
    request.session['concat_can_manage'] = access.get('can_manage', False)
    request.session['concat_can_rsvp'] = access.get('can_rsvp', False)
    request.session['concat_is_admin'] = access.get('can_manage', False)
    request.session.modified = True
    request.session.save()


def clear_concat_session(request):
    for key in SESSION_KEYS:
        request.session.pop(key, None)
