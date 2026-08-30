from django.conf import settings


class DisableGzipForCalendarFeedsMiddleware:
    """Google Calendar cannot subscribe to gzip-compressed ICS feeds."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.endswith('.ics'):
            request.META['HTTP_ACCEPT_ENCODING'] = 'identity'
        return self.get_response(request)


class ConcatOAuthCallbackMiddleware:
    """Handle ConCat OAuth redirects that land on paths other than /concat/callback/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.CONCAT_ENABLED
            and request.method == 'GET'
            and request.GET.get('code')
            and not request.path.rstrip('/').endswith('/concat/callback')
        ):
            from .concat.views import concat_callback
            return concat_callback(request)
        return self.get_response(request)
