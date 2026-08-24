from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from squallyline.image_utils import delete_file, optimize_image_field, validate_image_upload
from .models import Profile


@receiver(pre_save, sender=Profile)
def prepare_profile_picture(sender, instance, **kwargs):
    instance._old_profile_picture = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).only('profile_pic').first()
        if old and old.profile_pic and old.profile_pic.name != getattr(instance.profile_pic, 'name', None):
            instance._old_profile_picture = old.profile_pic.name
    if instance.profile_pic and not getattr(instance.profile_pic, '_committed', True):
        validate_image_upload(instance.profile_pic)
    optimize_image_field(instance.profile_pic, 1200)


@receiver(post_save, sender=Profile)
def remove_replaced_profile_picture(sender, instance, **kwargs):
    old_name = getattr(instance, '_old_profile_picture', None)
    if old_name:
        storage = instance.profile_pic.storage
        transaction.on_commit(lambda: storage.delete(old_name))


@receiver(post_delete, sender=Profile)
def remove_profile_picture(sender, instance, **kwargs):
    if instance.profile_pic:
        transaction.on_commit(lambda: delete_file(instance.profile_pic))
