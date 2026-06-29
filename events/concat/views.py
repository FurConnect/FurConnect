from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

from ..navigation import sanitize_next_url
from .access import resolve_concat_access
from .exceptions import ConcatError
from .oauth import exchange_code_for_token, get_authorize_url
from .oauth_state import pack_oauth_state, unpack_oauth_state
from .profiles import parse_concat_user
from .session import clear_concat_session, store_concat_session
from .users import get_user


def concat_login(request):
    if not settings.CONCAT_ENABLED:
        messages.error(request, 'ConCat sign-in is not enabled.')
        return redirect('events:schedule')

    next_url = sanitize_next_url(
        request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
    )
    return redirect(get_authorize_url(pack_oauth_state(next_url)))


def concat_callback(request):
    if not settings.CONCAT_ENABLED:
        messages.error(request, 'ConCat sign-in is not enabled.')
        return redirect('events:schedule')

    error = request.GET.get('error')
    if error:
        messages.error(request, f'ConCat sign-in failed: {error}')
        return redirect('/')

    state = request.GET.get('state')
    next_url = unpack_oauth_state(state) if state else None
    if not next_url:
        messages.error(request, 'Invalid or expired ConCat sign-in state. Please try again.')
        return redirect('/')

    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Missing ConCat authorization code.')
        return redirect(next_url)

    try:
        token_data = exchange_code_for_token(code)
        access_token = token_data.get('access_token')
        if not access_token:
            raise ConcatError('Missing access token in ConCat response')

        user_data = get_user(access_token)
        profile = parse_concat_user(user_data)
        if not profile['user_id']:
            raise ConcatError('Missing user id in ConCat response')

        try:
            access = resolve_concat_access(profile['user_id'], user_data=user_data)
        except ConcatError:
            access = {
                'role_names': profile.get('role_names', []),
                'can_manage': False,
                'skip_rsvp': False,
                'can_rsvp': not settings.CONCAT_REQUIRE_PAID_REGISTRATION,
            }

        store_concat_session(request, profile, access)
        display_name = profile['display_name']

        if access['skip_rsvp']:
            messages.success(request, f'Signed in with ConCat as {display_name}.')
        elif access['can_rsvp']:
            messages.success(request, f'Signed in with ConCat as {display_name}. You can RSVP to panels.')
        else:
            messages.warning(
                request,
                'Signed in with ConCat, but your account is not eligible to RSVP to panels.',
            )
    except ConcatError as exc:
        messages.error(request, str(exc))

    return redirect(next_url)


def concat_logout(request):
    clear_concat_session(request)
    messages.success(request, 'Signed out of ConCat.')
    return redirect(request.META.get('HTTP_REFERER', '/'))
