from django.shortcuts import render

# Create your views here.
# products/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from squallyline.permissions import IsAdminRole
from .models import (
    Category, Tag, Product, Style, ProductImage, StyleImage,
    ProductLike, StyleLike, ProductSaved, StyleSaved,
    ProductReview, ProductReviewImage, StyleReview, StyleReviewImage
)
from .serializers import (
    CategorySerializer, TagSerializer, ProductListSerializer, ProductDetailSerializer,
    StyleListSerializer, StyleDetailSerializer, ProductCreateUpdateSerializer,
    StyleCreateUpdateSerializer, ProductReviewSerializer, StyleReviewSerializer,
    ProductImageSerializer, StyleImageSerializer
)


# ========== HELPER FUNCTIONS ==========

def paginate_queryset(request, queryset, serializer_class, per_page=20):
    """Helper function to paginate queryset"""
    page = request.query_params.get('page', 1)
    per_page = int(request.query_params.get('per_page', per_page))
    
    # Cap per_page to prevent abuse
    if per_page > 100:
        per_page = 100
    
    paginator = Paginator(queryset, per_page)
    
    try:
        paginated = paginator.page(page)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)
    
    serializer = serializer_class(paginated, many=True, context={'request': request})
    
    return {
        'count': paginator.count,
        'total_pages': paginator.num_pages,
        'current_page': paginated.number,
        'per_page': per_page,
        'results': serializer.data
    }


# ========== CATEGORY VIEWS ==========

@api_view(['GET'])
@permission_classes([AllowAny])
def list_categories(request):
    """List active categories, optionally as a nested tree"""
    parent_id = request.query_params.get('parent', None)
    categories = Category.objects.filter(is_active=True)

    if parent_id:
        categories = categories.filter(parent_id=parent_id)
    else:
        categories = categories.filter(parent__isnull=True)

    categories = categories.order_by('order', 'name')

    # ?tree=true nests each category's children inline, so the storefront can
    # draw the whole navigation from one request instead of N+1 detail calls.
    want_tree = request.query_params.get('tree', '').lower() == 'true'
    try:
        depth = min(int(request.query_params.get('depth', 2)), 5)
    except (TypeError, ValueError):
        depth = 2

    serializer = CategorySerializer(
        categories,
        many=True,
        context={'with_children': want_tree, 'children_depth': depth},
    )
    return Response({
        'status': 'success',
        'count': categories.count(),
        'categories': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def category_detail(request, slug):
    """Get category details with subcategories"""
    category = get_object_or_404(Category, slug=slug, is_active=True)
    serializer = CategorySerializer(category)
    
    subcategories = category.subcategories.filter(is_active=True).order_by('order', 'name')
    sub_serializer = CategorySerializer(subcategories, many=True)
    
    return Response({
        'status': 'success',
        'category': serializer.data,
        'subcategories': sub_serializer.data
    }, status=status.HTTP_200_OK)


# ========== PRODUCT VIEWS ==========

@api_view(['GET'])
@permission_classes([AllowAny])
def list_products(request):
    """List products with filtering, search, and pagination"""
    products = Product.objects.filter(is_active=True)
    
    # Search
    search = request.query_params.get('search', '')
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(tags__name__icontains=search)
        ).distinct()
    
    # Filters
    # A parent slug has to match its children too — products hang off leaf
    # categories, so filtering on "men" alone would return nothing.
    category = request.query_params.get('category')
    if category:
        parent = Category.objects.filter(slug=category, is_active=True).first()
        if parent:
            products = products.filter(category_id__in=parent.descendant_ids())
        else:
            products = products.none()

    gender = request.query_params.get('gender')
    if gender:
        products = products.filter(gender=gender)
    
    size = request.query_params.get('size')
    if size:
        products = products.filter(size=size)
    
    min_price = request.query_params.get('min_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    
    max_price = request.query_params.get('max_price')
    if max_price:
        products = products.filter(price__lte=max_price)
    
    is_on_sale = request.query_params.get('on_sale')
    if is_on_sale and is_on_sale.lower() == 'true':
        products = products.filter(discount_price__isnull=False)
    
    is_featured = request.query_params.get('featured')
    if is_featured and is_featured.lower() == 'true':
        products = products.filter(is_featured=True)
    
    in_stock = request.query_params.get('in_stock')
    if in_stock and in_stock.lower() == 'true':
        products = products.filter(is_in_stock=True, stock_quantity__gt=0)
    
    tags = request.query_params.get('tags')
    if tags:
        tag_list = tags.split(',')
        products = products.filter(tags__slug__in=tag_list).distinct()
    
    # Ordering
    ordering = request.query_params.get('ordering', '-created_at')
    valid_orderings = ['price', '-price', 'created_at', '-created_at', 
                       'views', '-views', 'name', '-name', 'likes_count', '-likes_count']
    if ordering in valid_orderings:
        products = products.order_by(ordering)
    else:
        products = products.order_by('-created_at')
    
    return Response(paginate_queryset(request, products, ProductListSerializer))


@api_view(['GET'])
@permission_classes([AllowAny])
def product_detail(request, slug):
    """Get product details"""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # Increment views
    product.increment_views()
    
    # Get related products (same category)
    related = Product.objects.filter(
        category=product.category, 
        is_active=True
    ).exclude(id=product.id)[:8]
    
    serializer = ProductDetailSerializer(product, context={'request': request})
    related_serializer = ProductListSerializer(related, many=True, context={'request': request})
    
    return Response({
        'status': 'success',
        'product': serializer.data,
        'related_products': related_serializer.data
    }, status=status.HTTP_200_OK)


# ========== STYLE VIEWS ==========

@api_view(['GET'])
@permission_classes([AllowAny])
def list_styles(request):
    """List styles with filtering, search, and pagination"""
    styles = Style.objects.filter(is_active=True)
    
    # Search
    search = request.query_params.get('search', '')
    if search:
        styles = styles.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(tags__name__icontains=search)
        ).distinct()
    
    # Filters
    category = request.query_params.get('category')
    if category:
        parent = Category.objects.filter(slug=category, is_active=True).first()
        if parent:
            styles = styles.filter(category_id__in=parent.descendant_ids())
        else:
            styles = styles.none()

    gender = request.query_params.get('gender')
    if gender:
        styles = styles.filter(gender=gender)
    
    is_customizable = request.query_params.get('customizable')
    if is_customizable and is_customizable.lower() == 'true':
        styles = styles.filter(is_customizable=True)
    
    is_featured = request.query_params.get('featured')
    if is_featured and is_featured.lower() == 'true':
        styles = styles.filter(is_featured=True)
    
    tags = request.query_params.get('tags')
    if tags:
        tag_list = tags.split(',')
        styles = styles.filter(tags__slug__in=tag_list).distinct()
    
    # Ordering
    ordering = request.query_params.get('ordering', '-created_at')
    valid_orderings = ['created_at', '-created_at', 'views', '-views', 
                       'name', '-name', 'likes_count', '-likes_count']
    if ordering in valid_orderings:
        styles = styles.order_by(ordering)
    else:
        styles = styles.order_by('-created_at')
    
    return Response(paginate_queryset(request, styles, StyleListSerializer))


@api_view(['GET'])
@permission_classes([AllowAny])
def style_detail(request, slug):
    """Get style details"""
    style = get_object_or_404(Style, slug=slug, is_active=True)
    
    # Increment views
    style.increment_views()
    
    # Related styles (same category)
    related = Style.objects.filter(
        category=style.category, 
        is_active=True
    ).exclude(id=style.id)[:8]
    
    serializer = StyleDetailSerializer(style, context={'request': request})
    related_serializer = StyleListSerializer(related, many=True, context={'request': request})
    
    return Response({
        'status': 'success',
        'style': serializer.data,
        'related_styles': related_serializer.data
    }, status=status.HTTP_200_OK)


# ========== REVIEW VIEWS ==========

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_product_review(request, product_slug):
    """Create a review for a product"""
    product = get_object_or_404(Product, slug=product_slug, is_active=True)
    
    data = request.data.copy()
    data['product'] = str(product.id)
    
    serializer = ProductReviewSerializer(data=data, context={'request': request})
    if serializer.is_valid():
        review = serializer.save()
        for upload in request.FILES.getlist('images')[:5]:
            ProductReviewImage.objects.create(review=review, image=upload)
        return Response({
            'status': 'success',
            'message': 'Review submitted successfully. Awaiting approval.',
            'review': ProductReviewSerializer(review).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_style_review(request, style_slug):
    """Create a review for a style"""
    style = get_object_or_404(Style, slug=style_slug, is_active=True)
    
    data = request.data.copy()
    data['style'] = str(style.id)
    
    serializer = StyleReviewSerializer(data=data, context={'request': request})
    if serializer.is_valid():
        review = serializer.save()
        for upload in request.FILES.getlist('images')[:5]:
            StyleReviewImage.objects.create(review=review, image=upload)
        return Response({
            'status': 'success',
            'message': 'Review submitted successfully. Awaiting approval.',
            'review': StyleReviewSerializer(review).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_product_reviews(request, product_slug):
    """Get all approved reviews for a product"""
    product = get_object_or_404(Product, slug=product_slug)
    reviews = product.reviews.filter(is_approved=True).order_by('-created_at')
    
    return Response(paginate_queryset(request, reviews, ProductReviewSerializer))


@api_view(['GET'])
@permission_classes([AllowAny])
def get_style_reviews(request, style_slug):
    """Get all approved reviews for a style"""
    style = get_object_or_404(Style, slug=style_slug)
    reviews = style.reviews.filter(is_approved=True).order_by('-created_at')
    
    return Response(paginate_queryset(request, reviews, StyleReviewSerializer))


@api_view(['GET'])
@permission_classes([AllowAny])
def latest_reviews(request):
    """Newest approved reviews across products and styles.

    The homepage shows real customer words rather than placeholder copy, so it
    needs one feed spanning both catalogues.
    """
    try:
        limit = min(int(request.query_params.get('limit', 6)), 24)
    except (TypeError, ValueError):
        limit = 6

    product_reviews = (
        ProductReview.objects.filter(is_approved=True)
        .select_related('product', 'user')
        .order_by('-created_at')[:limit]
    )
    style_reviews = (
        StyleReview.objects.filter(is_approved=True)
        .select_related('style', 'user')
        .order_by('-created_at')[:limit]
    )

    def flatten(review, item, item_type):
        return {
            'id': str(review.id),
            'item_type': item_type,
            'item_name': item.name,
            'item_slug': item.slug,
            'user_name': f"{review.user.first_name} {review.user.last_name}".strip() or review.user.username,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at,
        }

    merged = [flatten(r, r.product, 'product') for r in product_reviews]
    merged += [flatten(r, r.style, 'style') for r in style_reviews]
    merged.sort(key=lambda r: r['created_at'], reverse=True)
    merged = merged[:limit]

    return Response({
        'status': 'success',
        'count': len(merged),
        'reviews': merged,
    }, status=status.HTTP_200_OK)


# ========== LIKE & SAVE VIEWS ==========

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_product_like(request, product_slug):
    """Toggle like on a product"""
    product = get_object_or_404(Product, slug=product_slug, is_active=True)
    
    like, created = ProductLike.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if not created:
        like.delete()
        product.likes_count = product.likes.filter().count()
        product.save(update_fields=['likes_count'])
        return Response({
            'status': 'success',
            'message': 'Product unliked',
            'is_liked': False
        }, status=status.HTTP_200_OK)
    
    product.likes_count = product.likes.filter().count()
    product.save(update_fields=['likes_count'])
    
    return Response({
        'status': 'success',
        'message': 'Product liked',
        'is_liked': True
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_style_like(request, style_slug):
    """Toggle like on a style"""
    style = get_object_or_404(Style, slug=style_slug, is_active=True)
    
    like, created = StyleLike.objects.get_or_create(
        user=request.user,
        style=style
    )
    
    if not created:
        like.delete()
        style.likes_count = style.likes.filter().count()
        style.save(update_fields=['likes_count'])
        return Response({
            'status': 'success',
            'message': 'Style unliked',
            'is_liked': False
        }, status=status.HTTP_200_OK)
    
    style.likes_count = style.likes.filter().count()
    style.save(update_fields=['likes_count'])
    
    return Response({
        'status': 'success',
        'message': 'Style liked',
        'is_liked': True
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_product_save(request, product_slug):
    """Toggle save on a product"""
    product = get_object_or_404(Product, slug=product_slug, is_active=True)
    
    saved, created = ProductSaved.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if not created:
        saved.delete()
        return Response({
            'status': 'success',
            'message': 'Product removed from saved',
            'is_saved': False
        }, status=status.HTTP_200_OK)
    
    return Response({
        'status': 'success',
        'message': 'Product saved',
        'is_saved': True
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_style_save(request, style_slug):
    """Toggle save on a style"""
    style = get_object_or_404(Style, slug=style_slug, is_active=True)
    
    saved, created = StyleSaved.objects.get_or_create(
        user=request.user,
        style=style
    )
    
    if not created:
        saved.delete()
        return Response({
            'status': 'success',
            'message': 'Style removed from saved',
            'is_saved': False
        }, status=status.HTTP_200_OK)
    
    return Response({
        'status': 'success',
        'message': 'Style saved',
        'is_saved': True
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_saved_products(request):
    """Get all products saved by the current user"""
    saved = ProductSaved.objects.filter(user=request.user).select_related('product')
    products = [s.product for s in saved]
    
    return Response(paginate_queryset(request, products, ProductListSerializer))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_saved_styles(request):
    """Get all styles saved by the current user"""
    saved = StyleSaved.objects.filter(user=request.user).select_related('style')
    styles = [s.style for s in saved]
    
    return Response(paginate_queryset(request, styles, StyleListSerializer))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_liked_products(request):
    """Get all products liked by the current user"""
    likes = ProductLike.objects.filter(user=request.user).select_related('product')
    products = [l.product for l in likes]
    
    return Response(paginate_queryset(request, products, ProductListSerializer))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_liked_styles(request):
    """Get all styles liked by the current user"""
    likes = StyleLike.objects.filter(user=request.user).select_related('style')
    styles = [l.style for l in likes]
    
    return Response(paginate_queryset(request, styles, StyleListSerializer))


# ========== ADMIN VIEWS ==========

@api_view(['GET', 'POST'])
@permission_classes([IsAdminRole])
def admin_categories(request):
    if request.method == 'GET':
        rows = Category.objects.all().select_related('parent').order_by('order', 'name')
        return Response({'status': 'success', 'categories': CategorySerializer(rows, many=True).data})

    serializer = CategorySerializer(data=request.data)
    if serializer.is_valid():
        category = serializer.save()
        return Response({'status': 'success', 'category': CategorySerializer(category).data}, status=status.HTTP_201_CREATED)
    return Response({'status': 'error', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
@permission_classes([IsAdminRole])
def admin_category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    if request.method == 'GET':
        return Response({'status': 'success', 'category': CategorySerializer(category).data})
    if request.method == 'DELETE':
        if category.products.exists() or category.styles.exists() or category.subcategories.exists():
            return Response(
                {'status': 'error', 'message': 'Move or delete the items in this category first.'},
                status=status.HTTP_409_CONFLICT,
            )
        category.delete()
        return Response({'status': 'success', 'message': 'Category deleted successfully'})

    data = request.data.copy()
    remove_image = str(data.pop('remove_image', '')).lower() in ('1', 'true', 'yes')
    serializer = CategorySerializer(category, data=data, partial=request.method == 'PATCH')
    if serializer.is_valid():
        updated = serializer.save()
        if remove_image and updated.image:
            updated.image = None
            updated.save(update_fields=['image', 'updated_at'])
        return Response({'status': 'success', 'category': CategorySerializer(updated).data})
    return Response({'status': 'error', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAdminRole])
def create_product(request):
    """Admin: Create a new product"""
    data = request.data.copy()
    primary_image = data.pop('primary_image', None)
    primary_image = primary_image[0] if isinstance(primary_image, list) else primary_image
    serializer = ProductCreateUpdateSerializer(data=data)
    if serializer.is_valid():
        product = serializer.save()
        if primary_image:
            ProductImage.objects.create(product=product, image=primary_image, is_primary=True)
        return Response({
            'status': 'success',
            'message': 'Product created successfully',
            'product': ProductDetailSerializer(product).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAdminRole])
def update_product(request, slug):
    """Admin: Update a product"""
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'GET':
        return Response({'status': 'success', 'product': ProductDetailSerializer(product, context={'request': request}).data})
    
    data = request.data.copy()
    primary_image = data.pop('primary_image', None)
    primary_image = primary_image[0] if isinstance(primary_image, list) else primary_image
    serializer = ProductCreateUpdateSerializer(
        product,
        data=data,
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        updated = serializer.save()
        if primary_image:
            updated.images.filter(is_primary=True).update(is_primary=False)
            ProductImage.objects.create(product=updated, image=primary_image, is_primary=True)
        return Response({
            'status': 'success',
            'message': 'Product updated successfully',
            'product': ProductDetailSerializer(updated).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAdminRole])
def delete_product(request, slug):
    """Admin: Delete a product"""
    product = get_object_or_404(Product, slug=slug)
    product.delete()
    return Response({
        'status': 'success',
        'message': 'Product deleted successfully'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminRole])
def create_style(request):
    """Admin: Create a new style"""
    data = request.data.copy()
    primary_image = data.pop('primary_image', None)
    primary_image = primary_image[0] if isinstance(primary_image, list) else primary_image
    serializer = StyleCreateUpdateSerializer(data=data)
    if serializer.is_valid():
        style = serializer.save()
        if primary_image:
            StyleImage.objects.create(style=style, image=primary_image, is_primary=True)
        return Response({
            'status': 'success',
            'message': 'Style created successfully',
            'style': StyleDetailSerializer(style).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAdminRole])
def update_style(request, slug):
    """Admin: Update a style"""
    style = get_object_or_404(Style, slug=slug)
    
    data = request.data.copy()
    primary_image = data.pop('primary_image', None)
    primary_image = primary_image[0] if isinstance(primary_image, list) else primary_image
    serializer = StyleCreateUpdateSerializer(
        style,
        data=data,
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        updated = serializer.save()
        if primary_image:
            updated.images.filter(is_primary=True).update(is_primary=False)
            StyleImage.objects.create(style=updated, image=primary_image, is_primary=True)
        return Response({
            'status': 'success',
            'message': 'Style updated successfully',
            'style': StyleDetailSerializer(updated).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAdminRole])
def delete_style(request, slug):
    """Admin: Delete a style"""
    style = get_object_or_404(Style, slug=slug)
    style.delete()
    return Response({
        'status': 'success',
        'message': 'Style deleted successfully'
    }, status=status.HTTP_200_OK)


def _upload_gallery_images(parent, files, image_model, relation_name, parent_field):
    current_count = getattr(parent, relation_name).count()
    if current_count + len(files) > 12:
        raise ValueError('A catalogue item can have up to 12 images.')
    created = []
    for index, upload in enumerate(files):
        created.append(image_model.objects.create(
            **{parent_field: parent},
            image=upload,
            alt_text=parent.name,
            order=current_count + index,
            is_primary=current_count == 0 and index == 0,
        ))
    return created


@api_view(['GET', 'POST'])
@permission_classes([IsAdminRole])
def manage_product_images(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        files = request.FILES.getlist('images') or ([request.FILES['image']] if 'image' in request.FILES else [])
        if not files:
            return Response({'status': 'error', 'message': 'Choose at least one image.'}, status=400)
        try: _upload_gallery_images(product, files, ProductImage, 'images', 'product')
        except ValueError as error: return Response({'status': 'error', 'message': str(error)}, status=400)
    return Response({'status': 'success', 'images': ProductImageSerializer(product.images.all(), many=True).data})


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAdminRole])
def manage_product_image(request, slug, image_id):
    product = get_object_or_404(Product, slug=slug); image = get_object_or_404(product.images, id=image_id)
    if request.method == 'DELETE':
        was_primary = image.is_primary; image.delete()
        if was_primary and product.images.exists(): product.images.update(is_primary=False); first = product.images.first(); first.is_primary = True; first.save(update_fields=['is_primary'])
        return Response(status=204)
    with transaction.atomic():
        if request.data.get('is_primary') in (True, 'true', 'True', '1'): product.images.update(is_primary=False)
        serializer = ProductImageSerializer(image, data=request.data, partial=True); serializer.is_valid(raise_exception=True); serializer.save()
    return Response({'status': 'success', 'image': serializer.data})


@api_view(['GET', 'POST'])
@permission_classes([IsAdminRole])
def manage_style_images(request, slug):
    style = get_object_or_404(Style, slug=slug)
    if request.method == 'GET':
        return Response({'status': 'success', 'style': StyleDetailSerializer(style, context={'request': request}).data})
    if request.method == 'POST':
        files = request.FILES.getlist('images') or ([request.FILES['image']] if 'image' in request.FILES else [])
        if not files: return Response({'status': 'error', 'message': 'Choose at least one image.'}, status=400)
        try: _upload_gallery_images(style, files, StyleImage, 'images', 'style')
        except ValueError as error: return Response({'status': 'error', 'message': str(error)}, status=400)
    return Response({'status': 'success', 'images': StyleImageSerializer(style.images.all(), many=True).data})


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAdminRole])
def manage_style_image(request, slug, image_id):
    style = get_object_or_404(Style, slug=slug); image = get_object_or_404(style.images, id=image_id)
    if request.method == 'DELETE':
        was_primary = image.is_primary; image.delete()
        if was_primary and style.images.exists(): style.images.update(is_primary=False); first = style.images.first(); first.is_primary = True; first.save(update_fields=['is_primary'])
        return Response(status=204)
    with transaction.atomic():
        if request.data.get('is_primary') in (True, 'true', 'True', '1'): style.images.update(is_primary=False)
        serializer = StyleImageSerializer(image, data=request.data, partial=True); serializer.is_valid(raise_exception=True); serializer.save()
    return Response({'status': 'success', 'image': serializer.data})
