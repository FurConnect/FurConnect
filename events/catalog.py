from django.db.models import Count, Max, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .concat import build_avatar_map, serialize_panel_host
from .models import Convention, Panel, PanelHost, Room, Tag


def convention_catalog_version(convention):
    panel_agg = Panel.objects.filter(convention_day__convention=convention).aggregate(
        latest=Max('updated_at'),
        total=Count('id'),
    )
    latest = panel_agg['latest'] or convention.updated_at
    host_count = PanelHost.objects.count()
    room_count = Room.objects.filter(convention=convention).count()
    tag_count = (
        Tag.objects.filter(panels__convention_day__convention=convention)
        .distinct()
        .count()
    )
    stamp = int(latest.timestamp()) if latest else 0
    return f'{stamp}:{panel_agg["total"]}:{host_count}:{room_count}:{tag_count}'


def serialize_host_panel(panel):
    tags = list(panel.tags.all())
    tag_color = tags[0].color if tags else '#ffffff'
    day_date = panel.convention_day.date if panel.convention_day and panel.convention_day.date else None
    return {
        'id': panel.pk,
        'title': panel.title,
        'description': panel.description,
        'start_time': panel.start_time.strftime('%I:%M %p') if panel.start_time else '',
        'end_time': panel.end_time.strftime('%I:%M %p') if panel.end_time else '',
        'room_name': panel.room.name if panel.room else '',
        'tag_color': tag_color,
        'cancelled': panel.cancelled,
        'day_of_week': day_date.strftime('%A') if day_date else '',
        '_sort_date': day_date,
        '_sort_time': panel.start_time,
    }


def sorted_host_panels(panels):
    panels_data = [serialize_host_panel(panel) for panel in panels]
    panels_data.sort(key=lambda item: (item['_sort_date'], item['_sort_time']))
    for item in panels_data:
        item.pop('_sort_date', None)
        item.pop('_sort_time', None)
    return panels_data


def _convention_panels_prefetch(convention):
    return Prefetch(
        'panels',
        queryset=(
            Panel.objects.filter(convention_day__convention=convention)
            .select_related('convention_day', 'room')
            .prefetch_related('tags')
            .order_by('convention_day__date', 'start_time')
        ),
        to_attr='convention_panels',
    )


def serialize_catalog_host(host, concat_avatars, *, selected_host_ids=None, include_panels=True):
    payload = serialize_panel_host(host, concat_avatars)
    if selected_host_ids is not None:
        payload['selected'] = host.pk in selected_host_ids
    if include_panels:
        panels_data = sorted_host_panels(getattr(host, 'convention_panels', []))
        payload['panels'] = panels_data
        payload['panels_count'] = len(panels_data)
    return payload


def _selected_host_ids(panel_id):
    if not panel_id:
        return set()
    try:
        panel = Panel.objects.get(pk=panel_id)
    except (Panel.DoesNotExist, ValueError, TypeError):
        return set()
    return set(panel.host.values_list('id', flat=True))


def build_convention_catalog(convention, *, panel_id=None, all_hosts=False, include_panels=True):
    """One payload of hosts/rooms/tags for a convention, reused by pages and AJAX."""
    selected_host_ids = _selected_host_ids(panel_id) if panel_id else None
    hosts = PanelHost.objects.order_by('name')
    if not all_hosts:
        hosts = hosts.filter(panels__convention_day__convention=convention).distinct()
    if include_panels:
        hosts = hosts.prefetch_related(_convention_panels_prefetch(convention))

    hosts = list(hosts)
    concat_avatars = build_avatar_map(hosts)
    hosts_data = [
        serialize_catalog_host(
            host,
            concat_avatars,
            selected_host_ids=selected_host_ids,
            include_panels=include_panels,
        )
        for host in hosts
    ]

    rooms = (
        Room.objects.filter(convention=convention)
        .order_by('sort_order', 'name')
        .values('id', 'name', 'sort_order')
    )
    tags = (
        Tag.objects.filter(panels__convention_day__convention=convention)
        .distinct()
        .order_by('name')
        .values('id', 'name', 'color')
    )

    return {
        'version': convention_catalog_version(convention),
        'convention_id': convention.pk,
        'hosts': hosts_data,
        'rooms': list(rooms),
        'tags': list(tags),
    }


def build_public_host_catalog(convention):
    return build_convention_catalog(convention, include_panels=True, all_hosts=False)


def build_panel_form_catalog(convention, panel_id=None):
    return build_convention_catalog(
        convention,
        panel_id=panel_id,
        all_hosts=True,
        include_panels=False,
    )


@require_GET
def get_convention_catalog_ajax(request, convention_pk):
    convention = get_object_or_404(Convention, pk=convention_pk)
    catalog = build_public_host_catalog(convention)
    response = JsonResponse(catalog)
    response['Cache-Control'] = 'private, max-age=60'
    return response
