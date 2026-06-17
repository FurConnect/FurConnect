from django.conf import settings


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
            from .views import concat_callback
            return concat_callback(request)
        return self.get_response(request)
