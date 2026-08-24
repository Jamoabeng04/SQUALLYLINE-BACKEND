from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(Category)
admin.site.register(Tag)
admin.site.register(Product)
admin.site.register(Style)
admin.site.register(ProductImage)
admin.site.register(StyleImage)
admin.site.register(ProductLike)
admin.site.register(StyleLike)
admin.site.register(ProductSaved)
admin.site.register(StyleSaved)
admin.site.register(ProductReview)
admin.site.register(ProductReviewImage)
admin.site.register(StyleReview)
admin.site.register(StyleReviewImage)