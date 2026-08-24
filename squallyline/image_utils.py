import os
import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


def validate_image_upload(upload):
    """Reject oversized, corrupt, or disguised non-image uploads."""
    if getattr(upload, 'size', 0) > MAX_IMAGE_BYTES:
        raise ValidationError('Images must be 12 MB or smaller.')
    try:
        image = Image.open(upload)
        width, height = image.size
        if width * height > MAX_IMAGE_PIXELS:
            raise ValidationError('This image has too many pixels. Use an image under 40 megapixels.')
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError('Upload a valid JPG, PNG, or WebP image.')
    finally:
        if hasattr(upload, 'seek'):
            upload.seek(0)


def optimize_image_field(field_file, max_dimension=2400):
    """Normalize a newly uploaded image to an oriented, web-sized WebP."""
    if not field_file or getattr(field_file, '_committed', True):
        return
    image = ImageOps.exif_transpose(Image.open(field_file))
    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGB')
    output = BytesIO()
    image.save(output, format='WEBP', quality=88, method=6)
    stem = os.path.splitext(os.path.basename(field_file.name))[0]
    field_file.save(f'{stem}-{uuid.uuid4().hex[:8]}.webp', ContentFile(output.getvalue()), save=False)


def delete_file(field_file):
    if field_file and field_file.name:
        field_file.storage.delete(field_file.name)
