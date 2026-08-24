# products/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    # Categories
    path('categories/', list_categories, name='list-categories'),
    path('categories/<slug:slug>/', category_detail, name='category-detail'),
    
    # Products
    path('products/', list_products, name='list-products'),
    path('products/<slug:slug>/', product_detail, name='product-detail'),
    path('products/<slug:product_slug>/reviews/', get_product_reviews, name='product-reviews'),
    path('products/<slug:product_slug>/review/', create_product_review, name='create-product-review'),
    path('products/<slug:product_slug>/like/', toggle_product_like, name='toggle-product-like'),
    path('products/<slug:product_slug>/save/', toggle_product_save, name='toggle-product-save'),
    
    # Styles
    path('styles/', list_styles, name='list-styles'),
    path('styles/<slug:slug>/', style_detail, name='style-detail'),
    path('styles/<slug:style_slug>/reviews/', get_style_reviews, name='style-reviews'),
    path('styles/<slug:style_slug>/review/', create_style_review, name='create-style-review'),
    path('styles/<slug:style_slug>/like/', toggle_style_like, name='toggle-style-like'),
    path('styles/<slug:style_slug>/save/', toggle_style_save, name='toggle-style-save'),
    
    # Reviews across both catalogues
    path('reviews/latest/', latest_reviews, name='latest-reviews'),

    # My saved/liked items
    path('my/saved-products/', my_saved_products, name='my-saved-products'),
    path('my/saved-styles/', my_saved_styles, name='my-saved-styles'),
    path('my/liked-products/', my_liked_products, name='my-liked-products'),
    path('my/liked-styles/', my_liked_styles, name='my-liked-styles'),
    
    # Admin
    path('admin/categories/', admin_categories, name='admin-categories'),
    path('admin/categories/<slug:slug>/', admin_category_detail, name='admin-category-detail'),
    path('admin/products/create/', create_product, name='create-product'),
    path('admin/products/<slug:slug>/update/', update_product, name='update-product'),
    path('admin/products/<slug:slug>/delete/', delete_product, name='delete-product'),
    path('admin/products/<slug:slug>/images/', manage_product_images, name='manage-product-images'),
    path('admin/products/<slug:slug>/images/<uuid:image_id>/', manage_product_image, name='manage-product-image'),
    path('admin/styles/create/', create_style, name='create-style'),
    path('admin/styles/<slug:slug>/update/', update_style, name='update-style'),
    path('admin/styles/<slug:slug>/delete/', delete_style, name='delete-style'),
    path('admin/styles/<slug:slug>/images/', manage_style_images, name='manage-style-images'),
    path('admin/styles/<slug:slug>/images/<uuid:image_id>/', manage_style_image, name='manage-style-image'),
]
