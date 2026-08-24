# orders/admin_urls.py
from django.urls import path
from .admin_views import *

urlpatterns = [
    path('dashboard/overview/', get_dashboard_overview, name='dashboard-overview'),
    path('dashboard/revenue-chart/', get_revenue_chart_data, name='revenue-chart'),
    path('dashboard/order-analytics/', get_order_analytics, name='order-analytics'),
    path('dashboard/production-analytics/', get_production_analytics, name='production-analytics'),
    path('dashboard/customer-analytics/', get_customer_analytics, name='customer-analytics'),
    path('dashboard/export/', get_export_data, name='export-data'),
]