from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save

from squallyline.image_utils import delete_file, optimize_image_field, validate_image_upload
from .models import Category, ProductImage, StyleImage, ProductReviewImage, StyleReviewImage


IMAGE_MODELS = (Category, ProductImage, StyleImage, ProductReviewImage, StyleReviewImage)


def prepare_image(sender, instance, **kwargs):
    field = instance.image
    instance._old_image_name = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).only('image').first()
        if old and old.image and old.image.name != getattr(field, 'name', None):
            instance._old_image_name = old.image.name
    if field and not getattr(field, '_committed', True):
        validate_image_upload(field)
    optimize_image_field(field, 2600 if sender in (ProductImage, StyleImage) else 1800)


def remove_replaced_image(sender, instance, **kwargs):
    old_name = getattr(instance, '_old_image_name', None)
    if old_name:
        storage = instance.image.storage
        transaction.on_commit(lambda: storage.delete(old_name))


def remove_deleted_image(sender, instance, **kwargs):
    field = instance.image
    if field and field.name:
        transaction.on_commit(lambda: delete_file(field))


for model in IMAGE_MODELS:
    pre_save.connect(prepare_image, sender=model, dispatch_uid=f'prepare-{model.__name__}-image')
    post_save.connect(remove_replaced_image, sender=model, dispatch_uid=f'replace-{model.__name__}-image')
    post_delete.connect(remove_deleted_image, sender=model, dispatch_uid=f'delete-{model.__name__}-image')
