# orders/admin_views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Sum, Count, Q, Avg, F
from squallyline.permissions import IsAdminRole, IsStaffRole
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Order, OrderItem, Transaction, User
from products.models import Product, Style, Category, ProductLike, StyleLike
from appointments.models import Appointment, AppointmentTier
from .admin_serializers import *
from .serializers import OrderListSerializer


@api_view(['GET'])
@permission_classes([IsStaffRole])
def get_dashboard_overview(request):
    """Get complete dashboard overview for admin"""
    
    today = timezone.now().date()
    week_start = today - timedelta(days=7)
    month_start = today - timedelta(days=30)
    year_start = today - timedelta(days=365)
    
    # ========== REVENUE STATS ==========
    paid_orders = Order.objects.filter(payment_status='paid')
    
    revenue_today = paid_orders.filter(order_date__date=today).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    revenue_week = paid_orders.filter(order_date__date__gte=week_start).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    revenue_month = paid_orders.filter(order_date__date__gte=month_start).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    revenue_year = paid_orders.filter(order_date__date__gte=year_start).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    revenue_total = paid_orders.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    revenue_pending = Order.objects.filter(payment_status='pending').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    revenue_stats = {
        'today': revenue_today,
        'this_week': revenue_week,
        'this_month': revenue_month,
        'this_year': revenue_year,
        'total': revenue_total,
        'pending': revenue_pending
    }
    
    # ========== ORDER STATS ==========
    order_stats = {
        'total': Order.objects.count(),
        'pending': Order.objects.filter(status='pending').count(),
        'confirmed': Order.objects.filter(status='confirmed').count(),
        'processing': Order.objects.filter(status='processing').count(),
        'ready': Order.objects.filter(status='ready').count(),
        'completed': Order.objects.filter(status='completed').count(),
        'cancelled': Order.objects.filter(status='cancelled').count(),
        'refunded': Order.objects.filter(status='refunded').count(),
    }
    
    # ========== PAYMENT STATS ==========
    payment_stats = {
        'paid': Order.objects.filter(payment_status='paid').count(),
        'pending': Order.objects.filter(payment_status='pending').count(),
        'failed': Order.objects.filter(payment_status='failed').count(),
        'refunded': Order.objects.filter(payment_status='refunded').count(),
        'partial': Order.objects.filter(payment_status='partial').count(),
        'by_method': {}
    }
    
    # Payment by method
    methods = Transaction.objects.filter(status='success').values('payment_method').annotate(count=Count('id'))
    for method in methods:
        payment_stats['by_method'][method['payment_method']] = method['count']
    
    # ========== PRODUCTION STATS ==========
    style_items = OrderItem.objects.filter(item_type='style')
    production_stats = {
        'pending': style_items.filter(production_stage='pending').count(),
        'pattern_making': style_items.filter(production_stage='pattern_making').count(),
        'cutting': style_items.filter(production_stage='cutting').count(),
        'sewing': style_items.filter(production_stage='sewing').count(),
        'fitting': style_items.filter(production_stage='fitting').count(),
        'finishing': style_items.filter(production_stage='finishing').count(),
        'quality_check': style_items.filter(production_stage='quality_check').count(),
        'ready': style_items.filter(production_stage='ready').count(),
        'completed': style_items.filter(production_stage='completed').count(),
        'total_in_progress': style_items.filter(
            production_stage__in=['pattern_making', 'cutting', 'sewing', 'fitting', 'finishing', 'quality_check']
        ).count()
    }
    
    # ========== PRODUCT STATS ==========
    # Top selling products. OrderItem stores the name it was bought under in
    # `item_name` (there is no product_name column) so the report survives the
    # product later being renamed or deleted.
    top_products = OrderItem.objects.filter(
        item_type='product',
        order__payment_status='paid'
    ).values('item_name').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_price')
    ).order_by('-total_quantity')[:10]
    
    # Top viewed products
    top_viewed_products = Product.objects.filter(is_active=True).order_by('-views')[:10].values(
        'id', 'name', 'slug', 'views'
    )
    
    # Top liked products
    top_liked_products = Product.objects.filter(is_active=True).order_by('-likes_count')[:10].values(
        'id', 'name', 'slug', 'likes_count'
    )
    
    product_stats = {
        'top_selling': list(top_products),
        'top_viewed': list(top_viewed_products),
        'top_liked': list(top_liked_products),
        'out_of_stock': Product.objects.filter(stock_quantity=0, is_active=True).count(),
        'low_stock': Product.objects.filter(stock_quantity__lte=5, stock_quantity__gt=0, is_active=True).count(),
        'total_products': Product.objects.filter(is_active=True).count()
    }
    
    # ========== STYLE STATS ==========
    # Top ordered styles
    top_styles = OrderItem.objects.filter(
        item_type='style',
        order__payment_status='paid'
    ).values('item_name').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_price')
    ).order_by('-total_quantity')[:10]
    
    # Top viewed styles
    top_viewed_styles = Style.objects.filter(is_active=True).order_by('-views')[:10].values(
        'id', 'name', 'slug', 'views'
    )
    
    # Top liked styles
    top_liked_styles = Style.objects.filter(is_active=True).order_by('-likes_count')[:10].values(
        'id', 'name', 'slug', 'likes_count'
    )
    
    style_stats = {
        'top_ordered': list(top_styles),
        'top_viewed': list(top_viewed_styles),
        'top_liked': list(top_liked_styles),
        'total_styles': Style.objects.filter(is_active=True).count()
    }
    
    # ========== APPOINTMENT STATS ==========
    appointment_stats = {
        'total': Appointment.objects.count(),
        'pending': Appointment.objects.filter(status='pending').count(),
        'confirmed': Appointment.objects.filter(status='confirmed').count(),
        'in_progress': Appointment.objects.filter(status='in_progress').count(),
        'completed': Appointment.objects.filter(status='completed').count(),
        'cancelled': Appointment.objects.filter(status='cancelled').count(),
        'no_show': Appointment.objects.filter(status='no_show').count(),
        'by_tier': {},
        'by_type': {}
    }
    
    # Appointments by tier
    tiers = Appointment.objects.values('tier__name').annotate(count=Count('id'))
    for tier in tiers:
        appointment_stats['by_tier'][tier['tier__name'] or 'Unknown'] = tier['count']
    
    # Appointments by type
    types = Appointment.objects.values('appointment_type').annotate(count=Count('id'))
    for apt_type in types:
        appointment_stats['by_type'][apt_type['appointment_type']] = apt_type['count']
    
    # ========== CUSTOMER STATS ==========
    customers = User.objects.filter(role='customer')
    customer_stats = {
        'total': customers.count(),
        'active': customers.filter(is_active=True).count(),
        'new_this_month': customers.filter(date_joined__date__gte=month_start).count(),
        'repeat_customers': User.objects.filter(
            orders__status__in=['confirmed', 'processing', 'ready', 'completed'],
            role='customer'
        ).annotate(order_count=Count('orders')).filter(order_count__gt=1).count(),
        'top_customers': []
    }
    
    # Top customers by spending
    top_customers = User.objects.filter(
        orders__payment_status='paid',
        role='customer'
    ).annotate(
        total_spent=Sum('orders__total'),
        order_count=Count('orders')
    ).filter(total_spent__gt=0).order_by('-total_spent')[:10].values(
        'id', 'email', 'username', 'total_spent', 'order_count'
    )
    customer_stats['top_customers'] = list(top_customers)
    
    # ========== RECENT ORDERS ==========
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:15]
    recent_serializer = OrderListSerializer(recent_orders, many=True)
    
    # ========== DAILY REVENUE (Last 30 days) ==========
    daily_revenue = []
    for i in range(30):
        date = today - timedelta(days=i)
        daily_total = Order.objects.filter(
            payment_status='paid',
            order_date__date=date
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        daily_count = Order.objects.filter(order_date__date=date).count()
        daily_revenue.append({
            'date': date,
            'revenue': daily_total,
            'orders': daily_count
        })
    daily_revenue.reverse()
    
    # ========== CATEGORY PERFORMANCE ==========
    categories = Category.objects.filter(parent__isnull=True)
    category_performance = []
    
    for category in categories:
        total_orders = OrderItem.objects.filter(
            order__payment_status='paid',
            item_type='product',
            snapshot__category_id=str(category.id)
        ).count()
        total_revenue = OrderItem.objects.filter(
            order__payment_status='paid',
            item_type='product',
            snapshot__category_id=str(category.id)
        ).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
        total_items = OrderItem.objects.filter(
            order__payment_status='paid',
            item_type='product',
            snapshot__category_id=str(category.id)
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Also check styles in this category
        style_orders = OrderItem.objects.filter(
            order__payment_status='paid',
            item_type='style',
            snapshot__category_id=str(category.id)
        ).count()
        
        category_performance.append({
            'category_name': category.name,
            'total_orders': total_orders + style_orders,
            'total_revenue': total_revenue,
            'total_items': total_items
        })
    
    category_performance.sort(key=lambda x: x['total_revenue'], reverse=True)
    
    # ========== RESPONSE ==========
    return Response({
        'status': 'success',
        'overview': {
            'revenue': revenue_stats,
            'orders': order_stats,
            'payments': payment_stats,
            'production': production_stats,
            'products': product_stats,
            'styles': style_stats,
            'appointments': appointment_stats,
            'customers': customer_stats,
            'recent_orders': recent_serializer.data,
            'daily_revenue': daily_revenue,
            'category_performance': category_performance[:10]
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_revenue_chart_data(request):
    """Get revenue data for charts"""
    period = request.query_params.get('period', '30')
    
    try:
        days = int(period)
        if days > 365:
            days = 365
    except ValueError:
        days = 30
    
    today = timezone.now().date()
    start_date = today - timedelta(days=days)
    
    chart_data = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        daily_total = Order.objects.filter(
            payment_status='paid',
            order_date__date=date
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        order_count = Order.objects.filter(order_date__date=date).count()
        
        chart_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'revenue': float(daily_total),
            'orders': order_count
        })
    
    return Response({
        'status': 'success',
        'period': days,
        'data': chart_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsStaffRole])
def get_order_analytics(request):
    """Get detailed order analytics"""
    # Order status distribution
    status_distribution = Order.objects.values('status').annotate(count=Count('id'))
    
    # Order type distribution
    type_distribution = Order.objects.values('order_type').annotate(count=Count('id'))
    
    # Average order value
    avg_order_value = Order.objects.filter(payment_status='paid').aggregate(
        avg=Avg('total')
    )['avg'] or Decimal('0.00')
    
    # Total orders this month vs last month
    today = timezone.now().date()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    
    orders_this_month = Order.objects.filter(order_date__date__gte=month_start).count()
    orders_last_month = Order.objects.filter(
        order_date__date__gte=last_month_start,
        order_date__date__lt=month_start
    ).count()
    
    growth = 0
    if orders_last_month > 0:
        growth = ((orders_this_month - orders_last_month) / orders_last_month) * 100
    
    # Revenue this month vs last month
    revenue_this_month = Order.objects.filter(
        payment_status='paid',
        order_date__date__gte=month_start
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    revenue_last_month = Order.objects.filter(
        payment_status='paid',
        order_date__date__gte=last_month_start,
        order_date__date__lt=month_start
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    revenue_growth = 0
    if revenue_last_month > 0:
        revenue_growth = ((revenue_this_month - revenue_last_month) / revenue_last_month) * 100
    
    return Response({
        'status': 'success',
        'analytics': {
            'status_distribution': list(status_distribution),
            'type_distribution': list(type_distribution),
            'average_order_value': float(avg_order_value),
            'orders': {
                'this_month': orders_this_month,
                'last_month': orders_last_month,
                'growth_percentage': round(growth, 1)
            },
            'revenue': {
                'this_month': float(revenue_this_month),
                'last_month': float(revenue_last_month),
                'growth_percentage': round(revenue_growth, 1)
            }
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsStaffRole])
def get_production_analytics(request):
    """Get production analytics for style orders"""
    # Production stage distribution
    stage_distribution = OrderItem.objects.filter(
        item_type='style'
    ).values('production_stage').annotate(count=Count('id'))
    
    # Average production time
    completed_items = OrderItem.objects.filter(
        item_type='style',
        production_stage='completed'
    )
    
    # Estimated vs actual completion
    production_times = []
    for item in completed_items[:50]:
        created_at = item.created_at
        completed_at = item.updated_at
        days_taken = (completed_at - created_at).days
        production_times.append(days_taken)
    
    avg_production_days = sum(production_times) / len(production_times) if production_times else 0
    
    # Items by order type
    items_by_type = OrderItem.objects.values('item_type').annotate(count=Count('id'))
    
    return Response({
        'status': 'success',
        'analytics': {
            'stage_distribution': list(stage_distribution),
            'average_production_days': round(avg_production_days, 1),
            'total_production_items': OrderItem.objects.filter(item_type='style').count(),
            'completed_items': completed_items.count(),
            'items_by_type': list(items_by_type)
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_customer_analytics(request):
    """Get customer analytics"""
    customers = User.objects.filter(role='customer')
    
    # Customer acquisition by month
    today = timezone.now().date()
    month_start = today.replace(day=1)
    last_6_months = []
    
    for i in range(6):
        month = month_start.replace(day=1) - timedelta(days=i*30)
        next_month = (month + timedelta(days=32)).replace(day=1)
        count = customers.filter(date_joined__date__gte=month, date_joined__date__lt=next_month).count()
        last_6_months.append({
            'month': month.strftime('%B %Y'),
            'new_customers': count
        })
    last_6_months.reverse()
    
    # Customer retention
    repeat_customers = User.objects.filter(
        role='customer',
        orders__status__in=['confirmed', 'processing', 'ready', 'completed']
    ).annotate(order_count=Count('orders')).filter(order_count__gt=1).count()
    
    total_customers_with_orders = User.objects.filter(
        role='customer',
        orders__status__in=['confirmed', 'processing', 'ready', 'completed']
    ).distinct().count()
    
    retention_rate = (repeat_customers / total_customers_with_orders * 100) if total_customers_with_orders > 0 else 0
    
    # Customer lifetime value
    clv = Order.objects.filter(
        payment_status='paid',
        user__role='customer'
    ).values('user').annotate(
        total=Sum('total'),
        order_count=Count('id')
    ).aggregate(avg_clv=Avg('total'))['avg_clv'] or Decimal('0.00')
    
    return Response({
        'status': 'success',
        'analytics': {
            'total_customers': customers.count(),
            'active_customers': customers.filter(is_active=True).count(),
            'repeat_customers': repeat_customers,
            'retention_rate': round(retention_rate, 1),
            'average_customer_lifetime_value': float(clv),
            'acquisition_by_month': last_6_months
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminRole])
def get_export_data(request):
    """Export data for reporting"""
    export_type = request.query_params.get('type', 'orders')
    format_type = request.query_params.get('format', 'json')
    
    if export_type == 'orders':
        orders = Order.objects.select_related('user').order_by('-created_at')
        data = OrderListSerializer(orders, many=True).data
        
    elif export_type == 'products':
        products = Product.objects.filter(is_active=True)
        from products.serializers import ProductListSerializer
        data = ProductListSerializer(products, many=True).data
        
    elif export_type == 'styles':
        styles = Style.objects.filter(is_active=True)
        from products.serializers import StyleListSerializer
        data = StyleListSerializer(styles, many=True).data
        
    elif export_type == 'customers':
        customers = User.objects.filter(role='customer')
        from accounts.serializers import UserListSerializer
        data = UserListSerializer(customers, many=True).data
        
    elif export_type == 'revenue':
        today = timezone.now().date()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start = today - timedelta(days=30)
        
        if end_date:
            end = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end = today
        
        revenue_data = []
        current = start
        while current <= end:
            daily_total = Order.objects.filter(
                payment_status='paid',
                order_date__date=current
            ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
            revenue_data.append({
                'date': current.strftime('%Y-%m-%d'),
                'revenue': float(daily_total)
            })
            current += timedelta(days=1)
        data = revenue_data
    
    else:
        return Response({
            'status': 'error',
            'message': 'Invalid export type'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'status': 'success',
        'export_type': export_type,
        'count': len(data),
        'data': data
    }, status=status.HTTP_200_OK)