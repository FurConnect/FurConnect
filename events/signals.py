from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .catalog import invalidate_convention_catalogs
from .models import Convention, ConventionDay, Panel, PanelHost, PanelHostOrder, PanelTag, Room, Tag


def _invalidate_from_convention_id(convention_id):
    invalidate_convention_catalogs(convention_id)


@receiver(post_save, sender=Convention)
@receiver(post_delete, sender=Convention)
def convention_catalog_changed(sender, instance, **kwargs):
    _invalidate_from_convention_id(instance.pk)


@receiver(post_save, sender=ConventionDay)
@receiver(post_delete, sender=ConventionDay)
def convention_day_catalog_changed(sender, instance, **kwargs):
    _invalidate_from_convention_id(instance.convention_id)


@receiver(post_save, sender=Room)
@receiver(post_delete, sender=Room)
def room_catalog_changed(sender, instance, **kwargs):
    _invalidate_from_convention_id(instance.convention_id)


@receiver(post_save, sender=Panel)
@receiver(post_delete, sender=Panel)
def panel_catalog_changed(sender, instance, **kwargs):
    convention_id = getattr(getattr(instance, 'convention_day', None), 'convention_id', None)
    _invalidate_from_convention_id(convention_id)


@receiver(post_save, sender=PanelTag)
@receiver(post_delete, sender=PanelTag)
def panel_tag_catalog_changed(sender, instance, **kwargs):
    convention_id = getattr(
        getattr(getattr(instance, 'panel', None), 'convention_day', None),
        'convention_id',
        None,
    )
    _invalidate_from_convention_id(convention_id)


@receiver(post_save, sender=PanelHostOrder)
@receiver(post_delete, sender=PanelHostOrder)
def panel_host_order_catalog_changed(sender, instance, **kwargs):
    convention_id = getattr(
        getattr(getattr(instance, 'panel', None), 'convention_day', None),
        'convention_id',
        None,
    )
    _invalidate_from_convention_id(convention_id)


@receiver(post_save, sender=PanelHost)
@receiver(post_delete, sender=PanelHost)
@receiver(post_save, sender=Tag)
@receiver(post_delete, sender=Tag)
def shared_catalog_changed(sender, instance, **kwargs):
    invalidate_convention_catalogs()
