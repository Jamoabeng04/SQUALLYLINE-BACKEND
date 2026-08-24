# orders/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    # Cart
    path('cart/', get_cart, name='get-cart'),
    path('cart/add/', add_to_cart, name='add-to-cart'),
    path('cart/item/<uuid:item_id>/update/', update_cart_item, name='update-cart-item'),
    path('cart/item/<uuid:item_id>/remove/', remove_from_cart, name='remove-from-cart'),
    path('cart/clear/', clear_cart, name='clear-cart'),
    
    # Orders
    path('orders/create/', create_order, name='create-order'),
    path('orders/my/', my_orders, name='my-orders'),
    path('orders/<uuid:order_id>/', order_detail, name='order-detail'),
    path('orders/<uuid:order_id>/cancel/', cancel_order, name='cancel-order'),
    path('orders/<uuid:order_id>/history/', get_order_history, name='order-history'),
    
    # Admin Orders
    path('admin/orders/', admin_list_orders, name='admin-list-orders'),
    path('admin/orders/<uuid:order_id>/status/', admin_update_order_status, name='admin-update-order-status'),
    path('admin/orders/items/<uuid:order_item_id>/production/', admin_update_production_stage, name='admin-update-production'),
    path('admin/orders/items/<uuid:order_item_id>/production-history/', get_production_history, name='production-history'),
    path('admin/dashboard/stats/', get_order_dashboard_stats, name='order-dashboard-stats'),
    path('admin/production-queue/', production_queue, name='production-queue'),
    
    # Payments
    path('payments/initialize/', initialize_payment, name='initialize-payment'),
    path('payments/verify/', verify_payment, name='verify-payment'),
    path('payments/status/<str:reference>/', get_transaction_status, name='transaction-status'),
    
    # Webhook
    path('webhook/paystack/', paystack_webhook, name='paystack-webhook'),
]
