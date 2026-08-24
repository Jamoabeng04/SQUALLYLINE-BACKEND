from django.db import models

# Create your models here.
# products/models.py
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import User, Person, Measurement
from squallyline.image_utils import validate_image_upload


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True, validators=[validate_image_upload])
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'categories'
        ordering = ['order', 'name']
        unique_together = ['parent', 'slug']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    @property
    def is_subcategory(self):
        return self.parent is not None
    
    @property
    def full_path(self):
        if self.parent:
            return f"{self.parent.full_path} / {self.name}"
        return self.name

    def descendant_ids(self, include_self=True):
        """This category plus every active category beneath it.

        Products and styles are always attached to leaf categories, so any
        filter or count for a parent ("Men") has to walk down to its children
        or it comes back empty. Breadth-first with a depth guard, since the
        tree is self-referential and a bad row could otherwise loop forever.
        """
        ids = [self.id] if include_self else []
        frontier = [self.id]
        for _ in range(10):
            children = list(
                Category.objects.filter(parent_id__in=frontier, is_active=True)
                .values_list('id', flat=True)
            )
            if not children:
                break
            ids.extend(children)
            frontier = children
        return ids


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'tags'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('U', 'Unisex'),
        ('K', 'Kids'),
    )
    
    SIZE_CHOICES = (
        ('XS', 'Extra Small'),
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', 'XXL'),
        ('XXXL', 'XXXL'),
        ('CUSTOM', 'Custom'),
    )
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    tags = models.ManyToManyField(Tag, related_name='products', blank=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Product specifics
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='U')
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, default='M')
    stock_quantity = models.PositiveIntegerField(default=0)
    is_in_stock = models.BooleanField(default=True)
    
    # Measurements (standard sizes)
    bust_measurement = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="In inches")
    waist_measurement = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="In inches")
    hip_measurement = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="In inches")
    shoulder_measurement = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="In inches")
    
    # Tracking
    views = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def final_price(self):
        return self.discount_price if self.discount_price else self.price
    
    @property
    def is_on_sale(self):
        return self.discount_price is not None and self.discount_price < self.price
    
    def increment_views(self):
        self.views += 1
        self.save(update_fields=['views'])


class Style(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('U', 'Unisex'),
        ('K', 'Kids'),
    )
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='styles')
    tags = models.ManyToManyField(Tag, related_name='styles', blank=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    
    # Style specifics
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='U')
    is_customizable = models.BooleanField(default=True, help_text="Can customer request modifications")
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estimated_making_time = models.PositiveIntegerField(null=True, blank=True, help_text="Estimated days to make")
    
    # Media
    video_link = models.URLField(max_length=500, blank=True, help_text="YouTube or TikTok URL")
    
    # Tracking
    views = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'styles'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def increment_views(self):
        self.views += 1
        self.save(update_fields=['views'])


class ProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/', validators=[validate_image_upload])
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_images'
        ordering = ['order']
    
    def __str__(self):
        return f"{self.product.name} - Image {self.order}"


class StyleImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    style = models.ForeignKey(Style, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='styles/', validators=[validate_image_upload])
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'style_images'
        ordering = ['order']
    
    def __str__(self):
        return f"{self.style.name} - Image {self.order}"


class ProductLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_likes')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='likes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_likes'
        unique_together = ['user', 'product']
    
    def __str__(self):
        return f"{self.user.email} likes {self.product.name}"


class StyleLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='style_likes')
    style = models.ForeignKey(Style, on_delete=models.CASCADE, related_name='likes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'style_likes'
        unique_together = ['user', 'style']
    
    def __str__(self):
        return f"{self.user.email} likes {self.style.name}"


class ProductSaved(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='saved_by')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_saved'
        unique_together = ['user', 'product']
    
    def __str__(self):
        return f"{self.user.email} saved {self.product.name}"


class StyleSaved(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_styles')
    style = models.ForeignKey(Style, on_delete=models.CASCADE, related_name='saved_by')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'style_saved'
        unique_together = ['user', 'style']
    
    def __str__(self):
        return f"{self.user.email} saved {self.style.name}"


class ProductReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews')
    
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_reviews'
        ordering = ['-created_at']
        unique_together = ['product', 'user']
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name} - {self.rating}★"


class ProductReviewImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='review_images/', validators=[validate_image_upload])
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_review_images'
    
    def __str__(self):
        return f"Review image for {self.review.product.name}"


class StyleReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    style = models.ForeignKey(Style, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='style_reviews')
    
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'style_reviews'
        ordering = ['-created_at']
        unique_together = ['style', 'user']
    
    def __str__(self):
        return f"{self.user.email} - {self.style.name} - {self.rating}★"


class StyleReviewImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(StyleReview, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='style_review_images/', validators=[validate_image_upload])
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'style_review_images'
    
    def __str__(self):
        return f"Review image for {self.review.style.name}"
