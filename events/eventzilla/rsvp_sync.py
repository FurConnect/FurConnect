from ..models import PanelRSVP
from .identity import attendee_id_values


def sync_rsvp_metadata(account):
    attendee_ids = attendee_id_values(account.email)
    if not attendee_ids:
        return
    PanelRSVP.objects.filter(attendee_id__in=attendee_ids).update(
        display_name=account.display_name,
        avatar_url=account.get_avatar_display(),
    )
