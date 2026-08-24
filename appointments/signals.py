from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from squallyline.image_utils import delete_file, optimize_image_field, validate_image_upload
from .models import ProposalReferenceImage


@receiver(pre_save, sender=ProposalReferenceImage)
def prepare_reference_image(sender, instance, **kwargs):
    instance._old_image_name = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).only('image').first()
        if old and old.image and old.image.name != getattr(instance.image, 'name', None):
            instance._old_image_name = old.image.name
    if instance.image and not getattr(instance.image, '_committed', True):
        validate_image_upload(instance.image)
    optimize_image_field(instance.image, 2200)


@receiver(post_save, sender=ProposalReferenceImage)
def remove_replaced_reference(sender, instance, **kwargs):
    if getattr(instance, '_old_image_name', None):
        storage = instance.image.storage
        transaction.on_commit(lambda: storage.delete(instance._old_image_name))


@receiver(post_delete, sender=ProposalReferenceImage)
def remove_reference(sender, instance, **kwargs):
    if instance.image:
        transaction.on_commit(lambda: delete_file(instance.image))
