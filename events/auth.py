from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import quote


def can_manage_events(request):
    """ConCat organizers when integrated; Django staff users otherwise."""
    user = getattr(request, 'user', None)
    if settings.CONCAT_ENABLED:
        return bool(request.session.get('concat_can_manage'))
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
    )


def organizer_login_url(next_path):
    if settings.CONCAT_ENABLED:
        return f"{reverse('events:concat_login')}?next={quote(next_path)}"
    return f"{reverse('events:login')}?next={quote(next_path)}"


def organizer_required(view_func):
    """Require ConCat organizer access, or Django staff when ConCat is disabled."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if can_manage_events(request):
            return view_func(request, *args, **kwargs)

        if settings.CONCAT_ENABLED:
            messages.error(request, 'ConCat organizer sign-in is required.')
        else:
            messages.error(request, 'Staff login is required to manage events.')

        return redirect(organizer_login_url(request.get_full_path()))

    return wrapper


# Backwards-compatible alias
concat_organizer_required = organizer_required
