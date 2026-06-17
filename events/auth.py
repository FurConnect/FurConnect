from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import quote


def can_manage_events(request):
    """Only ConCat users with a manage role (e.g. events/staff) may manage conventions."""
    if not settings.CONCAT_ENABLED:
        return False
    return bool(request.session.get('concat_can_manage'))


def concat_organizer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if can_manage_events(request):
            return view_func(request, *args, **kwargs)

        messages.error(request, 'ConCat organizer sign-in is required.')
        return redirect(
            f"{reverse('events:concat_login')}?next={quote(request.get_full_path())}"
        )

    return wrapper
