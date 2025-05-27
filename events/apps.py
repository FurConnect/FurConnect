from django.apps import AppConfig
from django.contrib.admin import AdminSite


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'

    def ready(self):
        # Set default admin site titles
        AdminSite.site_header = "Convention Admin"
        AdminSite.site_title = "Convention Admin Portal"
        AdminSite.index_title = "Welcome to Convention Admin Portal"

        try:
            import events.templatetags.event_filters
        except ImportError:
            pass
