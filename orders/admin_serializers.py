# orders/admin_serializers.py
from rest_framework import serializers
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Order, OrderItem, Transaction, User
from products.models import Product, Style, Category
from appointments.models import Appointment

 
class RevenueStatsSerializer(serializers.Serializer):
    """Revenue statistics"""
    today = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_week = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_month = serializers.DecimalField(max_digits=15, decimal_places=2)
    this_year = serializers.DecimalField(max_digits=15, decimal_places=2)
    total = serializers.DecimalField(max_digits=15, decimal_places=2)
    pending = serializers.DecimalField(max_digits=15, decimal_places=2)


class OrderStatsSerializer(serializers.Serializer):
    """Order statistics"""
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    processing = serializers.IntegerField()
    ready = serializers.IntegerField()
    completed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    refunded = serializers.IntegerField()


class PaymentStatsSerializer(serializers.Serializer):
    """Payment statistics"""
    paid = serializers.IntegerField()
    pending = serializers.IntegerField()
    failed = serializers.IntegerField()
    refunded = serializers.IntegerField()
    partial = serializers.IntegerField()
    
    by_method = serializers.DictField(child=serializers.IntegerField())


class ProductionStatsSerializer(serializers.Serializer):
    """Production statistics for style orders"""
    pending = serializers.IntegerField()
    pattern_making = serializers.IntegerField()
    cutting = serializers.IntegerField()
    sewing = serializers.IntegerField()
    fitting = serializers.IntegerField()
    finishing = serializers.IntegerField()
    quality_check = serializers.IntegerField()
    ready = serializers.IntegerField()
    completed = serializers.IntegerField()
    total_in_progress = serializers.IntegerField()


class ProductStatsSerializer(serializers.Serializer):
    """Product performance statistics"""
    top_selling = serializers.ListField(child=serializers.DictField())
    top_viewed = serializers.ListField(child=serializers.DictField())
    top_liked = serializers.ListField(child=serializers.DictField())
    out_of_stock = serializers.IntegerField()
    low_stock = serializers.IntegerField()
    total_products = serializers.IntegerField()


class StyleStatsSerializer(serializers.Serializer):
    """Style performance statistics"""
    top_ordered = serializers.ListField(child=serializers.DictField())
    top_viewed = serializers.ListField(child=serializers.DictField())
    top_liked = serializers.ListField(child=serializers.DictField())
    total_styles = serializers.IntegerField()


class AppointmentStatsSerializer(serializers.Serializer):
    """Appointment statistics"""
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    completed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    no_show = serializers.IntegerField()
    
    by_tier = serializers.DictField(child=serializers.IntegerField())
    by_type = serializers.DictField(child=serializers.IntegerField())


class CustomerStatsSerializer(serializers.Serializer):
    """Customer statistics"""
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    new_this_month = serializers.IntegerField()
    repeat_customers = serializers.IntegerField()
    top_customers = serializers.ListField(child=serializers.DictField())


class DailyRevenueSerializer(serializers.Serializer):
    """Daily revenue for chart"""
    date = serializers.DateField()
    revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    orders = serializers.IntegerField()


class CategoryPerformanceSerializer(serializers.Serializer):
    """Category performance"""
    category_name = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_items = serializers.IntegerField()


class DashboardOverviewSerializer(serializers.Serializer):
    """Complete dashboard overview"""
    revenue = RevenueStatsSerializer()
    orders = OrderStatsSerializer()
    payments = PaymentStatsSerializer()
    production = ProductionStatsSerializer()
    products = ProductStatsSerializer()
    styles = StyleStatsSerializer()
    appointments = AppointmentStatsSerializer()
    customers = CustomerStatsSerializer()
    recent_orders = serializers.ListField(child=serializers.DictField())
    daily_revenue = DailyRevenueSerializer(many=True)
    category_performance = CategoryPerformanceSerializer(many=True)