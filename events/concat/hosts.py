from django.conf import settings

from .profiles import get_concat_profile_pictures


def apply_host_profile_image(host, image_base64):
    if image_base64:
        host.image = image_base64
    elif image_base64 == '' and host.image:
        host.image = None


def build_avatar_map(hosts):
    if not settings.CONCAT_ENABLED:
        return {}
    concat_ids = [
        host.concat_user_id for host in hosts
        if host.concat_user_id
    ]
    if not concat_ids:
        return {}
    return get_concat_profile_pictures(concat_ids)


def resolve_profile_picture(host, concat_avatars=None):
    if settings.CONCAT_ENABLED and host.concat_user_id:
        if concat_avatars is None:
            concat_avatars = build_avatar_map([host])
        avatar_url = concat_avatars.get(str(host.concat_user_id), '')
        if avatar_url:
            return avatar_url
    if host.image:
        return host.image
    return host.get_initials_avatar()


def serialize_panel_host(host, concat_avatars=None):
    if concat_avatars is None and host.concat_user_id:
        concat_avatars = build_avatar_map([host])
    return {
        'id': host.pk,
        'name': host.name,
        'concat_user_id': host.concat_user_id or '',
        'profile_picture': resolve_profile_picture(host, concat_avatars),
    }


def attach_host_avatar_urls(hosts):
    hosts = list(hosts)
    if not hosts:
        return hosts

    unique_hosts = {host.pk: host for host in hosts}
    concat_avatars = build_avatar_map(unique_hosts.values())
    for host in unique_hosts.values():
        host.avatar_url = resolve_profile_picture(host, concat_avatars)
    return hosts
