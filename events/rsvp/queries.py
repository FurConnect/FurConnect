from ..models import PanelRSVP
from .feed import get_rsvp_attendee_ids_for_request
from .identity import get_rsvp_attendee_ids


def filter_panels_for_user_rsvp(panels_qs, request, rsvp_param=None):
    attendee_ids = get_rsvp_attendee_ids_for_request(request, rsvp_param)
    if not attendee_ids:
        return panels_qs.none()
    panel_ids = PanelRSVP.objects.filter(
        attendee_id__in=attendee_ids,
        panel__in=panels_qs,
    ).values_list('panel_id', flat=True).distinct()
    return panels_qs.filter(pk__in=panel_ids)


def get_user_rsvp_panel_ids(request, convention):
    attendee_ids = get_rsvp_attendee_ids(request)
    if not attendee_ids:
        return set()
    return set(
        PanelRSVP.objects.filter(
            attendee_id__in=attendee_ids,
            panel__convention_day__convention=convention,
        ).values_list('panel_id', flat=True)
    )


def get_rsvp_attendees(panel):
    return [
        {
            'display_name': rsvp.display_name or rsvp.attendee_id,
            'avatar_url': rsvp.avatar_url,
        }
        for rsvp in panel.rsvps.all()
    ]
