# products/serializers.py
import re
from rest_framework import serializers
from django.db.models import Avg, Count
from .models import (
    Category, Tag, Product, Style, ProductImage, StyleImage,
    ProductLike, StyleLike, ProductSaved, StyleSaved,
    ProductReview, ProductReviewImage, StyleReview, StyleReviewImage
)


class CategorySerializer(serializers.ModelSerializer):
    subcategory_count = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    style_count = serializers.SerializerMethodField()
    subcategories = serializers.SerializerMethodField()
    full_path = serializers.CharField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'parent', 'name', 'slug', 'description', 'image',
                  'is_active', 'order', 'subcategory_count', 'product_count',
                  'style_count', 'subcategories', 'full_path',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_subcategory_count(self, obj):
        return obj.subcategories.filter(is_active=True).count()

    # Counts roll up the subtree, so "Men" reports everything hanging under it
    # rather than the zero it would show from its own direct rows.
    def get_product_count(self, obj):
        return Product.objects.filter(
            category_id__in=obj.descendant_ids(), is_active=True
        ).count()

    def get_style_count(self, obj):
        return Style.objects.filter(
            category_id__in=obj.descendant_ids(), is_active=True
        ).count()

    # Nested children are opt-in: the tree endpoint asks for them, detail and
    # write paths don't pay for the extra queries.
    def get_subcategories(self, obj):
        depth = self.context.get('children_depth', 0)
        if not self.context.get('with_children') or depth <= 0:
            return []
        children = obj.subcategories.filter(is_active=True).order_by('order', 'name')
        child_context = {**self.context, 'children_depth': depth - 1}
        return CategorySerializer(children, many=True, context=child_context).data


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']


class StyleImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StyleImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProductReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReviewImage
        fields = ['id', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']


class StyleReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StyleReviewImage
        fields = ['id', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProductReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    images = ProductReviewImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProductReview
        fields = ['id', 'product', 'user', 'user_name', 'rating', 'comment', 
                  'is_approved', 'images', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'is_approved', 'created_at', 'updated_at']
    
    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def validate(self, data):
        user = self.context.get('request').user
        product = data.get('product')
        
        if ProductReview.objects.filter(product=product, user=user).exists():
            raise serializers.ValidationError("You have already reviewed this product.")
        return data
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class StyleReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    images = StyleReviewImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = StyleReview
        fields = ['id', 'style', 'user', 'user_name', 'rating', 'comment', 
                  'is_approved', 'images', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'is_approved', 'created_at', 'updated_at']
    
    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def validate(self, data):
        user = self.context.get('request').user
        style = data.get('style')
        
        if StyleReview.objects.filter(style=style, user=user).exists():
            raise serializers.ValidationError("You have already reviewed this style.")
        return data
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ProductListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'category', 'category_name', 'category_slug', 'name', 'slug', 
                  'description', 'price', 'discount_price', 'final_price', 'is_on_sale',
                  'gender', 'size', 'stock_quantity', 'is_in_stock', 'primary_image',
                  'average_rating', 'review_count', 'views', 'likes_count', 'is_featured',
                  'is_liked', 'is_saved', 'created_at']
        read_only_fields = ['id', 'views', 'likes_count', 'created_at']
    
    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return ProductImageSerializer(primary).data
        first = obj.images.first()
        if first:
            return ProductImageSerializer(first).data
        return None
    
    def get_average_rating(self, obj):
        avg = obj.reviews.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else None
    
    def get_review_count(self, obj):
        return obj.reviews.filter(is_approved=True).count()
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ProductLike.objects.filter(product=obj, user=request.user).exists()
        return False
    
    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ProductSaved.objects.filter(product=obj, user=request.user).exists()
        return False


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    reviews = serializers.SerializerMethodField()
    
    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ['images', 'tags', 'reviews', 
                                                       'bust_measurement', 'waist_measurement', 
                                                       'hip_measurement', 'shoulder_measurement',
                                                       'updated_at']
    
    def get_reviews(self, obj):
        reviews = obj.reviews.filter(is_approved=True)[:10]
        return ProductReviewSerializer(reviews, many=True).data


class StyleListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    
    class Meta:
        model = Style
        fields = ['id', 'category', 'category_name', 'category_slug', 'name', 'slug', 
                  'description', 'gender', 'is_customizable', 'base_price', 
                  'estimated_making_time', 'video_link', 'primary_image',
                  'average_rating', 'review_count', 'views', 'likes_count', 
                  'is_featured', 'is_liked', 'is_saved', 'created_at']
        read_only_fields = ['id', 'views', 'likes_count', 'created_at']
    
    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return StyleImageSerializer(primary).data
        first = obj.images.first()
        if first:
            return StyleImageSerializer(first).data
        return None
    
    def get_average_rating(self, obj):
        avg = obj.reviews.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else None
    
    def get_review_count(self, obj):
        return obj.reviews.filter(is_approved=True).count()
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return StyleLike.objects.filter(style=obj, user=request.user).exists()
        return False
    
    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return StyleSaved.objects.filter(style=obj, user=request.user).exists()
        return False


class StyleDetailSerializer(StyleListSerializer):
    images = StyleImageSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    reviews = serializers.SerializerMethodField()
    
    class Meta(StyleListSerializer.Meta):
        fields = StyleListSerializer.Meta.fields + ['images', 'tags', 'reviews', 'updated_at']
    
    def get_reviews(self, obj):
        reviews = obj.reviews.filter(is_approved=True)[:10]
        return StyleReviewSerializer(reviews, many=True).data


# Admin create/update serializers
class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['id', 'views', 'likes_count', 'created_at', 'updated_at']
    
    def validate_tags(self, value):
        tag_objects = []
        for tag_name in value:
            tag, _ = Tag.objects.get_or_create(
                name=tag_name.strip(),
                defaults={'slug': tag_name.strip().lower().replace(' ', '-')}
            )
            tag_objects.append(tag)
        return tag_objects
    
    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        product = Product.objects.create(**validated_data)
        if tags:
            product.tags.set(tags)
        return product
    
    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance


class StyleCreateUpdateSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    
    class Meta:
        model = Style
        fields = '__all__'
        read_only_fields = ['id', 'views', 'likes_count', 'created_at', 'updated_at']
    
    def validate_tags(self, value):
        tag_objects = []
        for tag_name in value:
            tag, _ = Tag.objects.get_or_create(
                name=tag_name.strip(),
                defaults={'slug': tag_name.strip().lower().replace(' ', '-')}
            )
            tag_objects.append(tag)
        return tag_objects
    
    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        style = Style.objects.create(**validated_data)
        if tags:
            style.tags.set(tags)
        return style
    
    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance