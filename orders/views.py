from django.shortcuts import render

# Create your views here.
# orders/views.py
import uuid
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from squallyline.permissions import IsAdminRole, IsStaffRole
from .models import (
    Cart, CartItem, Order, OrderItem, Transaction, 
    OrderHistory, ProductionStageHistory, PaymentSchedule
)
from .serializers import (
    CartSerializer, CartItemSerializer, AddToCartSerializer,
    OrderListSerializer, OrderDetailSerializer, CreateOrderSerializer,
    OrderUpdateStatusSerializer, ProductionStageUpdateSerializer,
    TransactionSerializer, InitializePaymentSerializer, VerifyPaymentSerializer,
    OrderHistorySerializer, ProductionStageHistorySerializer,OrderItemSerializer,
)
from squallyline.paystack_utils import PaystackAPI, is_payment_successful
from appointments.models import Appointment

logger = logging.getLogger(__name__)


# ========== CART VIEWS ==========

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart(request):
    """Get current user's cart"""
    cart, created = Cart.objects.get_or_create(user=request.user)
    serializer = CartSerializer(cart, context={'request': request})
    return Response({
        'status': 'success',
        'cart': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart(request):
    """Add item to cart"""
    serializer = AddToCartSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        data = serializer.validated_data
        
        cart, _ = Cart.objects.get_or_create(user=request.user)
        
        # Check if item already exists in cart
        existing_item = None
        if data['item_type'] == 'product' and data.get('product'):
            existing_item = cart.items.filter(
                item_type='product',
                product=data['product']
            ).first()
        elif data['item_type'] == 'style' and data.get('style'):
            existing_item = cart.items.filter(
                item_type='style',
                style=data['style'],
                person=data.get('person'),
                measurement=data.get('measurement')
            ).first()
        elif data['item_type'] == 'appointment' and data.get('appointment'):
            existing_item = cart.items.filter(
                item_type='appointment',
                appointment=data['appointment']
            ).first()
        
        if existing_item:
            existing_item.quantity += data['quantity']
            existing_item.save()
            cart_item = existing_item
        else:
            cart_item = CartItem.objects.create(
                cart=cart,
                item_type=data['item_type'],
                product=data.get('product'),
                style=data.get('style'),
                appointment=data.get('appointment'),
                person=data.get('person'),
                measurement=data.get('measurement'),
                quantity=data['quantity'],
                price=data['price'],
                custom_name=data.get('custom_name', ''),
                custom_description=data.get('custom_description', ''),
                custom_fabric=data.get('custom_fabric', ''),
                custom_notes=data.get('custom_notes', ''),
            )
            
            # Save snapshots
            if data.get('product_snapshot'):
                cart_item.product_snapshot = data['product_snapshot']
            if data.get('style_snapshot'):
                cart_item.style_snapshot = data['style_snapshot']
            if data.get('appointment_snapshot'):
                cart_item.appointment_snapshot = data['appointment_snapshot']
            if data.get('person_snapshot'):
                cart_item.person_snapshot = data['person_snapshot']
            if data.get('measurement_snapshot'):
                cart_item.measurement_snapshot = data['measurement_snapshot']
            cart_item.save()
        
        return Response({
            'status': 'success',
            'message': 'Item added to cart',
            'cart_item': CartItemSerializer(cart_item, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_cart_item(request, item_id):
    """Update cart item quantity"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    quantity = request.data.get('quantity')
    if not quantity:
        return Response({
            'status': 'error',
            'message': 'Quantity is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        quantity = int(quantity)
        if quantity < 1:
            return Response({
                'status': 'error',
                'message': 'Quantity must be at least 1'
            }, status=status.HTTP_400_BAD_REQUEST)
    except ValueError:
        return Response({
            'status': 'error',
            'message': 'Quantity must be a number'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    cart_item.quantity = quantity
    cart_item.save()
    
    return Response({
        'status': 'success',
        'message': 'Cart item updated',
        'cart_item': CartItemSerializer(cart_item, context={'request': request}).data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    
    return Response({
        'status': 'success',
        'message': 'Item removed from cart'
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_cart(request):
    """Clear all items from cart"""
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart.clear()
    
    return Response({
        'status': 'success',
        'message': 'Cart cleared successfully'
    }, status=status.HTTP_200_OK)


# ========== ORDER VIEWS ==========

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """Create order from cart"""
    serializer = CreateOrderSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        order = serializer.save()
        
        # If order has appointments, update appointment status
        for item in order.items.all():
            if item.item_type == 'appointment':
                # Get the appointment from snapshot
                if item.snapshot and 'id' in item.snapshot:
                    try:
                        appointment = Appointment.objects.get(id=item.snapshot['id'])
                        appointment.status = 'confirmed'
                        appointment.save()
                    except Appointment.DoesNotExist:
                        pass
        
        return Response({
            'status': 'success',
            'message': 'Order created successfully',
            'order': OrderDetailSerializer(order, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_orders(request):
    """Get current user's orders"""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by status
    status_filter = request.query_params.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Filter by type
    type_filter = request.query_params.get('type')
    if type_filter:
        orders = orders.filter(order_type=type_filter)
    
    serializer = OrderListSerializer(orders, many=True)
    
    return Response({
        'status': 'success',
        'count': orders.count(),
        'orders': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id):
    """Get order details"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission
    if request.user.role not in ['admin', 'apprentice'] and order.user != request.user:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to view this order'
        }, status=status.HTTP_403_FORBIDDEN)
    
    today = timezone.now().date()
    overdue = order.payment_schedules.filter(
        status__in=['pending', 'overdue'], due_date__lt=today
    ).exists()
    if overdue != order.tracking_locked:
        order.tracking_locked = overdue
        order.save(update_fields=['tracking_locked', 'updated_at'])
    serializer = OrderDetailSerializer(order, context={'request': request})
    payload = serializer.data
    if order.tracking_locked and request.user.role not in ['admin', 'apprentice']:
        # Billing and support remain visible; workshop details are gated until payment.
        payload['items'] = [
            {key: item.get(key) for key in ('id', 'item_type', 'item_name', 'quantity', 'price', 'total_price')}
            for item in payload.get('items', [])
        ]
        payload['history'] = []
    
    return Response({
        'status': 'success',
        'order': payload,
        'payment_gate': {
            'locked': order.tracking_locked,
            'outstanding': str(max(Decimal('0'), order.total - order.amount_paid)),
            'due_date': order.balance_due_date,
            'next_schedule_id': str(order.payment_schedules.filter(status__in=['pending', 'overdue']).order_by('sequence').values_list('id', flat=True).first() or ''),
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_order(request, order_id):
    """Cancel order"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if not order.can_cancel:
        return Response({
            'status': 'error',
            'message': 'This order cannot be cancelled'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    old_status = order.status
    order.status = 'cancelled'
    order.save()
    
    OrderHistory.objects.create(
        order=order,
        old_status=old_status,
        new_status='cancelled',
        note='Order cancelled by user',
        changed_by=request.user
    )
    
    return Response({
        'status': 'success',
        'message': 'Order cancelled successfully'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsStaffRole])
def admin_list_orders(request):
    """Admin: List all orders"""
    orders = Order.objects.select_related('user').order_by('-created_at')
    
    # Filters
    status_filter = request.query_params.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    type_filter = request.query_params.get('type')
    if type_filter:
        orders = orders.filter(order_type=type_filter)
    
    payment_status = request.query_params.get('payment_status')
    if payment_status:
        orders = orders.filter(payment_status=payment_status)
    
    search = request.query_params.get('search')
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__username__icontains=search)
        )
    
    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    page = request.query_params.get('page', 1)
    per_page = int(request.query_params.get('per_page', 20))
    
    if per_page > 100:
        per_page = 100
    
    paginator = Paginator(orders, per_page)
    
    try:
        paginated = paginator.page(page)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)
    
    serializer = OrderListSerializer(paginated, many=True)
    
    return Response({
        'status': 'success',
        'count': paginator.count,
        'total_pages': paginator.num_pages,
        'current_page': paginated.number,
        'per_page': per_page,
        'orders': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsStaffRole])
def production_queue(request):
    """Deadline-first workshop queue, grouped by the agreed urgency."""
    active = Order.objects.filter(
        order_type__in=['style', 'custom'],
        status__in=['pending', 'confirmed', 'processing'],
    ).select_related('user').prefetch_related('items', 'payment_schedules').order_by(
        'estimated_delivery_date', 'created_at'
    )
    groups = {'express': [], 'priority': [], 'standard': []}
    today = timezone.now().date()
    for order in active:
        due = order.estimated_delivery_date
        days_remaining = (due - today).days if due else None
        row = OrderDetailSerializer(order, context={'request': request}).data
        row['days_remaining'] = days_remaining
        row['risk'] = (
            'payment_overdue' if order.tracking_locked else
            'production_overdue' if days_remaining is not None and days_remaining < 0 else
            'due_soon' if days_remaining is not None and days_remaining <= 3 else
            'awaiting_deposit' if order.amount_paid < order.deposit_required else 'on_track'
        )
        groups[order.priority].append(row)
    return Response({'status': 'success', 'queue': groups})


@api_view(['POST'])
@permission_classes([IsStaffRole])
def admin_update_order_status(request, order_id):
    """Admin: Update order status"""
    order = get_object_or_404(Order, id=order_id)
    
    serializer = OrderUpdateStatusSerializer(
        data=request.data,
        context={'order': order}
    )
    if serializer.is_valid():
        old_status = order.status
        new_status = serializer.validated_data['status']
        note = serializer.validated_data.get('note', '')
        
        order.status = new_status
        order.save()
        
        # If completed, set completion date
        if new_status == 'completed':
            order.completion_date = timezone.now()
            order.save()
        
        OrderHistory.objects.create(
            order=order,
            old_status=old_status,
            new_status=new_status,
            note=note or f'Status updated by admin to {order.get_status_display()}',
            changed_by=request.user
        )
        
        return Response({
            'status': 'success',
            'message': f'Order status updated to {order.get_status_display()}',
            'order': OrderDetailSerializer(order).data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsStaffRole])
def admin_update_production_stage(request, order_item_id):
    """Admin: Update production stage for style order item"""
    order_item = get_object_or_404(OrderItem, id=order_item_id, item_type='style')
    
    # Verify order is not cancelled
    if order_item.order.status == 'cancelled':
        return Response({
            'status': 'error',
            'message': 'Cannot update production stage for cancelled order'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = ProductionStageUpdateSerializer(
        data=request.data,
        context={'order_item': order_item}
    )
    if serializer.is_valid():
        old_stage = order_item.production_stage
        new_stage = serializer.validated_data['stage']
        note = serializer.validated_data.get('note', '')
        
        order_item.production_stage = new_stage
        if new_stage == 'completed':
            order_item.is_completed = True
        order_item.save()
        
        ProductionStageHistory.objects.create(
            order_item=order_item,
            old_stage=old_stage,
            new_stage=new_stage,
            note=note,
            changed_by=request.user
        )
        
        # If all items completed, update order status
        if all(item.is_completed for item in order_item.order.items.all()):
            order_item.order.status = 'completed'
            order_item.order.completion_date = timezone.now()
            order_item.order.save()
        
        return Response({
            'status': 'success',
            'message': f'Production stage updated to {new_stage}',
            'order_item': OrderItemSerializer(order_item).data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_order_history(request, order_id):
    """Get order status history"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.user.role not in ['admin', 'apprentice'] and order.user != request.user:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to view this history'
        }, status=status.HTTP_403_FORBIDDEN)
    
    history = order.history.all().order_by('-created_at')
    serializer = OrderHistorySerializer(history, many=True)
    
    return Response({
        'status': 'success',
        'count': history.count(),
        'history': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_production_history(request, order_item_id):
    """Get production stage history for a style order item"""
    order_item = get_object_or_404(OrderItem, id=order_item_id, item_type='style')
    
    # Check permission
    if request.user.role not in ['admin', 'apprentice'] and order_item.order.user != request.user:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to view this history'
        }, status=status.HTTP_403_FORBIDDEN)
    
    history = order_item.stage_history.all().order_by('-created_at')
    serializer = ProductionStageHistorySerializer(history, many=True)
    
    return Response({
        'status': 'success',
        'count': history.count(),
        'history': serializer.data
    }, status=status.HTTP_200_OK)


# ========== PAYMENT VIEWS ==========

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initialize_payment(request):
    """Initialize payment with Paystack"""
    serializer = InitializePaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    user = request.user
    payment_method = data.get('payment_method', 'paystack')
    
    # Get order or appointment
    order = None
    appointment = None
    amount = Decimal('0.00')
    
    schedule = None
    if data.get('schedule_id'):
        schedule = get_object_or_404(PaymentSchedule, id=data['schedule_id'], order__user=user)
        if schedule.status in ['paid', 'waived']:
            return Response({'status': 'error', 'message': 'This payment is already settled'}, status=status.HTTP_400_BAD_REQUEST)
        order = schedule.order
        amount = schedule.amount
    elif data.get('order_id'):
        order = get_object_or_404(Order, id=data['order_id'], user=user)
        schedule = order.payment_schedules.filter(status__in=['pending', 'overdue']).order_by('sequence').first()
        amount = schedule.amount if schedule else max(Decimal('0'), order.total - order.amount_paid)
    elif data.get('appointment_id'):
        appointment = get_object_or_404(Appointment, id=data['appointment_id'], user=user)
        amount = appointment.final_price or appointment.tier.fee
    
    if amount <= 0:
        return Response({
            'status': 'error',
            'message': 'Invalid payment amount'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Generate reference
    reference = f"PAY-{uuid.uuid4().hex[:12].upper()}"
    
    # Initialize Paystack transaction
    paystack = PaystackAPI()
    response = paystack.initialize_transaction(
        email=user.email,
        amount=float(amount),
        reference=reference
    )
    
    if not response.get('status'):
        return Response({
            'status': 'error',
            'message': response.get('message', 'Payment initialization failed')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create transaction record
    transaction_obj = Transaction.objects.create(
        order=order,
        user=user,
        appointment=appointment,
        transaction_type='payment',
        payment_method=payment_method,
        amount=amount,
        reference=reference,
        gateway_reference=response['data']['reference'],
        status='pending',
        gateway_response=response,
        metadata={
            'payment_method': payment_method,
            'order_id': str(order.id) if order else None,
            'appointment_id': str(appointment.id) if appointment else None,
            'schedule_id': str(schedule.id) if schedule else None,
        }
    )
    
    return Response({
        'status': 'success',
        'message': 'Payment initialized',
        'data': {
            'reference': reference,
            'transaction_id': str(transaction_obj.id),
            'authorization_url': response['data']['authorization_url'],
            'access_code': response['data']['access_code'],
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    """Verify payment status"""
    serializer = VerifyPaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    reference = serializer.validated_data['reference']
    
    # Get transaction
    try:
        transaction_obj = Transaction.objects.get(reference=reference, user=request.user)
    except Transaction.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Transaction not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Verify with Paystack
    paystack = PaystackAPI()
    response = paystack.verify_transaction(reference)
    
    if not response.get('status'):
        return Response({
            'status': 'error',
            'message': response.get('message', 'Verification failed')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if payment was successful
    if is_payment_successful(response):
        # Update transaction
        transaction_obj.status = 'success'
        transaction_obj.gateway_response = response
        transaction_obj.completed_at = timezone.now()
        transaction_obj.save()
        
        # Update order payment status
        if transaction_obj.order:
            order = transaction_obj.order
            schedule_id = (transaction_obj.metadata or {}).get('schedule_id')
            if schedule_id:
                PaymentSchedule.objects.filter(id=schedule_id).update(status='paid', paid_at=timezone.now())
            order.amount_paid = sum(t.amount for t in order.transactions.filter(status='success')) + transaction_obj.amount
            order.payment_status = 'paid' if order.amount_paid >= order.total else 'partial'
            order.tracking_locked = False
            if order.payment_status == 'paid': order.payment_date = timezone.now()
            order.save()
            
            # If order is style, update status to confirmed
            if order.order_type in ['style', 'custom']:
                order.status = 'confirmed'
                order.save()
        
        # Update appointment payment status
        if transaction_obj.appointment:
            appointment = transaction_obj.appointment
            appointment.is_paid = True
            appointment.save()
        
        return Response({
            'status': 'success',
            'message': 'Payment verified successfully',
            'payment_status': 'success',
            'transaction': TransactionSerializer(transaction_obj).data
        }, status=status.HTTP_200_OK)
    else:
        # Payment failed
        transaction_obj.status = 'failed'
        transaction_obj.gateway_response = response
        transaction_obj.save()
        
        return Response({
            'status': 'error',
            'message': 'Payment verification failed',
            'payment_status': 'failed',
            'transaction': TransactionSerializer(transaction_obj).data
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transaction_status(request, reference):
    """Get transaction status"""
    try:
        transaction_obj = Transaction.objects.get(reference=reference, user=request.user)
    except Transaction.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Transaction not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'status': 'success',
        'transaction': TransactionSerializer(transaction_obj).data
    }, status=status.HTTP_200_OK)


# ========== WEBHOOK VIEW ==========

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def paystack_webhook(request):
    """Handle Paystack webhook notifications"""
    try:
        payload = request.body
        signature = request.headers.get('x-paystack-signature')
        
        if not signature:
            logger.error("No signature provided in webhook request")
            return JsonResponse({'status': 'error', 'message': 'Missing signature'}, status=400)
        
        # Verify signature
        paystack = PaystackAPI()
        if not paystack.verify_webhook(payload, signature):
            logger.error("Invalid webhook signature")
            return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)
        
        # Parse payload
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        
        event = data.get('event')
        event_data = data.get('data', {})
        
        logger.info(f"Webhook received: {event} - Reference: {event_data.get('reference')}")
        
        # Handle charge success
        if event == 'charge.success':
            return handle_charge_success(event_data)
        
        # Handle charge failed
        elif event == 'charge.failed':
            return handle_charge_failed(event_data)
        
        # Handle transfer success
        elif event == 'transfer.success':
            return handle_transfer_success(event_data)
        
        # Handle transfer failed
        elif event == 'transfer.failed':
            return handle_transfer_failed(event_data)
        
        # Unsupported event
        logger.warning(f"Unsupported webhook event: {event}")
        return JsonResponse({'status': 'success', 'message': f'Unsupported event: {event}'}, status=200)
    
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def handle_charge_success(event_data):
    """Handle successful charge webhook"""
    reference = event_data.get('reference')
    amount = event_data.get('amount')
    
    if not reference:
        logger.error("No reference in webhook data")
        return JsonResponse({'status': 'error', 'message': 'No reference'}, status=400)
    
    try:
        with transaction.atomic():
            # Get transaction
            transaction_obj = Transaction.objects.get(reference=reference)
            
            # Check if already processed
            if transaction_obj.status == 'success':
                logger.info(f"Transaction {reference} already processed")
                return JsonResponse({'status': 'success', 'message': 'Already processed'}, status=200)
            
            # Update transaction
            transaction_obj.status = 'success'
            transaction_obj.gateway_response = event_data
            transaction_obj.completed_at = timezone.now()
            
            # Store payment method from gateway
            if 'channel' in event_data.get('authorization', {}):
                transaction_obj.payment_method = event_data['authorization']['channel']
            
            transaction_obj.save()
            
            # Update order
            if transaction_obj.order:
                order = transaction_obj.order
                order.payment_status = 'paid'
                order.payment_date = timezone.now()
                
                # If style/custom order, confirm it
                if order.order_type in ['style', 'custom']:
                    order.status = 'confirmed'
                
                order.save()
                
                # Create order history
                OrderHistory.objects.create(
                    order=order,
                    old_status=order.status,
                    new_status=order.status,
                    note='Payment confirmed via Paystack webhook',
                    changed_by=None
                )
            
            # Update appointment
            if transaction_obj.appointment:
                appointment = transaction_obj.appointment
                appointment.is_paid = True
                appointment.save()
            
            logger.info(f"Payment successful for transaction: {reference}")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Payment processed successfully'
            }, status=200)
    
    except Transaction.DoesNotExist:
        logger.error(f"Transaction not found: {reference}")
        return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def handle_charge_failed(event_data):
    """Handle failed charge webhook"""
    reference = event_data.get('reference')
    
    if not reference:
        logger.error("No reference in webhook data")
        return JsonResponse({'status': 'error', 'message': 'No reference'}, status=400)
    
    try:
        with transaction.atomic():
            transaction_obj = Transaction.objects.get(reference=reference)
            
            if transaction_obj.status != 'failed':
                transaction_obj.status = 'failed'
                transaction_obj.gateway_response = event_data
                transaction_obj.save()
                
                logger.info(f"Payment failed for transaction: {reference}")
            
            return JsonResponse({'status': 'success', 'message': 'Payment failed recorded'}, status=200)
    
    except Transaction.DoesNotExist:
        logger.error(f"Transaction not found: {reference}")
        return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def handle_transfer_success(event_data):
    """Handle successful transfer webhook"""
    reference = event_data.get('reference')
    logger.info(f"Transfer successful: {reference}")
    return JsonResponse({'status': 'success'}, status=200)


def handle_transfer_failed(event_data):
    """Handle failed transfer webhook"""
    reference = event_data.get('reference')
    logger.warning(f"Transfer failed: {reference}")
    return JsonResponse({'status': 'success'}, status=200)


# ========== DASHBOARD VIEW ==========

@api_view(['GET'])
@permission_classes([IsStaffRole])
def get_order_dashboard_stats(request):
    """Admin: Get order dashboard statistics"""
    from django.db.models import Sum, Count, Q
    
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    confirmed_orders = Order.objects.filter(status='confirmed').count()
    processing_orders = Order.objects.filter(status='processing').count()
    completed_orders = Order.objects.filter(status='completed').count()
    cancelled_orders = Order.objects.filter(status='cancelled').count()
    
    total_revenue = Order.objects.filter(
        payment_status='paid',
        status__in=['confirmed', 'processing', 'ready', 'completed']
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    pending_payments = Order.objects.filter(payment_status='pending').count()
    paid_orders = Order.objects.filter(payment_status='paid').count()
    
    # Style orders in production
    style_orders = OrderItem.objects.filter(
        item_type='style',
        production_stage__in=['pending', 'pattern_making', 'cutting', 'sewing', 'fitting', 'finishing']
    ).count()
    
    # Recent orders
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:10]
    recent_serializer = OrderListSerializer(recent_orders, many=True)
    
    return Response({
        'status': 'success',
        'stats': {
            'orders': {
                'total': total_orders,
                'pending': pending_orders,
                'confirmed': confirmed_orders,
                'processing': processing_orders,
                'completed': completed_orders,
                'cancelled': cancelled_orders,
            },
            'payments': {
                'total_revenue': str(total_revenue),
                'paid': paid_orders,
                'pending_payments': pending_payments,
            },
            'production': {
                'in_progress': style_orders,
            }
        },
        'recent_orders': recent_serializer.data
    }, status=status.HTTP_200_OK)
