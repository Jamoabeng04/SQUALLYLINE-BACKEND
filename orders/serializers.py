# orders/serializers.py
import uuid
from decimal import Decimal
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import (
    Cart, CartItem, Order, OrderItem, Transaction, 
    OrderHistory, ProductionStageHistory, PaymentSchedule
)
from accounts.models import User, Person, Measurement
from products.models import Product, Style
from appointments.models import Appointment


class CartItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(read_only=True)
    total_price = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    product_details = serializers.SerializerMethodField()
    style_details = serializers.SerializerMethodField()
    appointment_details = serializers.SerializerMethodField()
    person_details = serializers.SerializerMethodField()
    measurement_details = serializers.SerializerMethodField()
    
    class Meta:
        model = CartItem
        fields = ['id', 'item_type', 'product', 'product_details', 'style', 'style_details',
                  'appointment', 'appointment_details', 'person', 'person_details',
                  'measurement', 'measurement_details', 'quantity', 'price', 'total_price',
                  'item_name', 'custom_name', 'custom_description', 'custom_fabric',
                  'custom_notes', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_product_details(self, obj):
        if obj.product:
            from products.serializers import ProductListSerializer
            return ProductListSerializer(obj.product, context=self.context).data
        return None
    
    def get_style_details(self, obj):
        if obj.style:
            from products.serializers import StyleListSerializer
            return StyleListSerializer(obj.style, context=self.context).data
        return None
    
    def get_appointment_details(self, obj):
        if obj.appointment:
            from appointments.serializers import AppointmentListSerializer
            return AppointmentListSerializer(obj.appointment, context=self.context).data
        return None
    
    def get_person_details(self, obj):
        if obj.person:
            from accounts.serializers import PersonSerializer
            return PersonSerializer(obj.person).data
        return None
    
    def get_measurement_details(self, obj):
        if obj.measurement:
            from accounts.serializers import MeasurementSerializer
            return MeasurementSerializer(obj.measurement).data
        return None


class AddToCartSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=CartItem.ITEM_TYPE_CHOICES)
    product_id = serializers.UUIDField(required=False, allow_null=True)
    style_id = serializers.UUIDField(required=False, allow_null=True)
    appointment_id = serializers.UUIDField(required=False, allow_null=True)
    person_id = serializers.UUIDField(required=False, allow_null=True)
    measurement_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.IntegerField(default=1, min_value=1, max_value=100)
    custom_name = serializers.CharField(required=False, allow_blank=True)
    custom_description = serializers.CharField(required=False, allow_blank=True)
    custom_fabric = serializers.CharField(required=False, allow_blank=True)
    custom_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        item_type = data.get('item_type')
        user = self.context['request'].user
        
        # Validate based on item type
        if item_type == 'product':
            product_id = data.get('product_id')
            if not product_id:
                raise serializers.ValidationError({"product_id": "Product ID is required for product items."})
            
            try:
                product = Product.objects.get(id=product_id, is_active=True)
                data['product'] = product
                data['price'] = product.final_price
                # Snapshot product data
                data['product_snapshot'] = {
                    'id': str(product.id),
                    'name': product.name,
                    'slug': product.slug,
                    'price': str(product.price),
                    'discount_price': str(product.discount_price) if product.discount_price else None,
                    'final_price': str(product.final_price),
                    'description': product.description,
                    'gender': product.gender,
                    'size': product.size,
                    'stock_quantity': product.stock_quantity,
                    'category_id': str(product.category.id),
                    'category_name': product.category.name,
                    'is_on_sale': product.is_on_sale,
                }
                # Get primary image
                primary_image = product.images.filter(is_primary=True).first()
                if primary_image:
                    data['product_snapshot']['primary_image'] = primary_image.image.url if primary_image.image else None
            except Product.DoesNotExist:
                raise serializers.ValidationError({"product_id": "Product not found or inactive."})
        
        elif item_type == 'style':
            style_id = data.get('style_id')
            if not style_id:
                raise serializers.ValidationError({"style_id": "Style ID is required for style items."})
            
            try:
                style = Style.objects.get(id=style_id, is_active=True)
                data['style'] = style
                data['price'] = style.base_price
                # Snapshot style data
                data['style_snapshot'] = {
                    'id': str(style.id),
                    'name': style.name,
                    'slug': style.slug,
                    'description': style.description,
                    'base_price': str(style.base_price),
                    'gender': style.gender,
                    'is_customizable': style.is_customizable,
                    'estimated_making_time': style.estimated_making_time,
                    'category_id': str(style.category.id),
                    'category_name': style.category.name,
                    'video_link': style.video_link,
                }
                # Get primary image
                primary_image = style.images.filter(is_primary=True).first()
                if primary_image:
                    data['style_snapshot']['primary_image'] = primary_image.image.url if primary_image.image else None
            except Style.DoesNotExist:
                raise serializers.ValidationError({"style_id": "Style not found or inactive."})
            
            # For styles, person and measurement are required
            if not data.get('person_id'):
                raise serializers.ValidationError({"person_id": "Person is required for style orders."})
            if not data.get('measurement_id'):
                raise serializers.ValidationError({"measurement_id": "Measurement is required for style orders."})
            
            # Validate person belongs to user
            try:
                person = Person.objects.get(id=data['person_id'], user=user)
                data['person'] = person
                data['person_snapshot'] = {
                    'id': str(person.id),
                    'name': person.name,
                    'relationship': person.relationship,
                    'phone': person.phone,
                    'email': person.email,
                }
            except Person.DoesNotExist:
                raise serializers.ValidationError({"person_id": "Person not found or does not belong to you."})
            
            # Validate measurement belongs to person
            try:
                measurement = Measurement.objects.get(id=data['measurement_id'], person=person)
                data['measurement'] = measurement
                data['measurement_snapshot'] = {
                    'id': str(measurement.id),
                    'data': measurement.data,
                    'notes': measurement.notes,
                }
            except Measurement.DoesNotExist:
                raise serializers.ValidationError({"measurement_id": "Measurement not found for this person."})
        
        elif item_type == 'appointment':
            appointment_id = data.get('appointment_id')
            if not appointment_id:
                raise serializers.ValidationError({"appointment_id": "Appointment ID is required for appointment items."})
            
            try:
                appointment = Appointment.objects.get(id=appointment_id, user=user)
                data['appointment'] = appointment
                data['price'] = appointment.final_price or appointment.tier.fee
                data['appointment_snapshot'] = {
                    'id': str(appointment.id),
                    'appointment_type': appointment.appointment_type,
                    'tier': appointment.tier.name,
                    'tier_fee': str(appointment.tier.fee),
                    'final_price': str(appointment.final_price) if appointment.final_price else None,
                    'slot_date': str(appointment.slot.date),
                    'slot_time': f"{appointment.slot.start_time} - {appointment.slot.end_time}",
                    'estimated_completion_date': str(appointment.estimated_completion_date) if appointment.estimated_completion_date else None,
                    'status': appointment.status,
                }
            except Appointment.DoesNotExist:
                raise serializers.ValidationError({"appointment_id": "Appointment not found."})
        
        elif item_type == 'custom':
            if not data.get('custom_name'):
                raise serializers.ValidationError({"custom_name": "Custom name is required for custom items."})
            data['price'] = 0.00  # Price set by admin later
        
        return data


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    total = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    
    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total_items', 'subtotal', 'total', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class OrderListSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'user', 'user_name', 'order_type', 'order_type_display',
                  'subtotal', 'total', 'status', 'status_display', 'payment_status',
                  'payment_status_display', 'order_date', 'estimated_delivery_date',
                  'item_count', 'priority', 'amount_paid', 'deposit_required',
                  'balance_due_date', 'tracking_locked', 'created_at']
        read_only_fields = ['id', 'order_number', 'created_at']
    
    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    
    def get_item_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    transactions = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    
    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + [
            'items', 'transactions', 'history', 'discount', 'tax', 'shipping_fee',
            'shipping_address', 'shipping_city', 'shipping_state', 'shipping_country',
            'shipping_zip', 'shipping_phone', 'billing_address', 'billing_same_as_shipping',
            'tracking_number', 'tracking_url', 'courier', 'admin_notes', 'customer_notes',
            'payment_date', 'completion_date', 'updated_at', 'payment_schedules'
        ]

    payment_schedules = serializers.SerializerMethodField()

    def get_payment_schedules(self, obj):
        return PaymentScheduleSerializer(obj.payment_schedules.all(), many=True).data
    
    def get_transactions(self, obj):
        from .serializers import TransactionSerializer
        return TransactionSerializer(obj.transactions.all(), many=True).data
    
    def get_history(self, obj):
        return OrderHistorySerializer(obj.history.all(), many=True).data


class CreateOrderSerializer(serializers.Serializer):
    shipping_address = serializers.CharField(required=True)
    shipping_city = serializers.CharField(required=True)
    shipping_state = serializers.CharField(required=False, allow_blank=True)
    shipping_country = serializers.CharField(default='Ghana')
    shipping_zip = serializers.CharField(required=False, allow_blank=True)
    shipping_phone = serializers.CharField(required=True)
    billing_same_as_shipping = serializers.BooleanField(default=True)
    billing_address = serializers.CharField(required=False, allow_blank=True)
    customer_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        user = self.context['request'].user
        
        # Get or create cart
        cart, _ = Cart.objects.get_or_create(user=user)
        cart_items = cart.items.all()
        
        if not cart_items.exists():
            raise serializers.ValidationError("Cart is empty. Cannot create order.")
        
        data['cart'] = cart
        data['cart_items'] = cart_items
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        cart = validated_data['cart']
        cart_items = validated_data['cart_items']
        
        # Calculate totals
        subtotal = cart.subtotal
        
        # Check if any item is style or custom - determine order type
        order_type = 'product'
        for item in cart_items:
            if item.item_type == 'style':
                order_type = 'style'
                break
            elif item.item_type == 'custom':
                order_type = 'custom'
                break
            elif item.item_type == 'appointment':
                order_type = 'appointment'
                break
        
        # Create order
        order = Order.objects.create(
            user=user,
            order_type=order_type,
            subtotal=subtotal,
            discount=Decimal('0.00'),
            tax=Decimal('0.00'),
            shipping_fee=Decimal('0.00'),
            total=subtotal,
            shipping_address=validated_data['shipping_address'],
            shipping_city=validated_data['shipping_city'],
            shipping_state=validated_data.get('shipping_state', ''),
            shipping_country=validated_data.get('shipping_country', 'Ghana'),
            shipping_zip=validated_data.get('shipping_zip', ''),
            shipping_phone=validated_data['shipping_phone'],
            billing_same_as_shipping=validated_data.get('billing_same_as_shipping', True),
            billing_address=validated_data.get('billing_address', ''),
            customer_notes=validated_data.get('customer_notes', ''),
            status='pending',
            payment_status='pending'
        )
        
        # Create order items from cart items
        for cart_item in cart_items:
            snapshot = {}
            
            # Build snapshot based on item type
            if cart_item.item_type == 'product' and cart_item.product:
                snapshot = {
                    'id': str(cart_item.product.id),
                    'name': cart_item.product.name,
                    'slug': cart_item.product.slug,
                    'price': str(cart_item.product.price),
                    'discount_price': str(cart_item.product.discount_price) if cart_item.product.discount_price else None,
                    'final_price': str(cart_item.product.final_price),
                    'description': cart_item.product.description,
                    'gender': cart_item.product.gender,
                    'size': cart_item.product.size,
                    'category_name': cart_item.product.category.name if cart_item.product.category else None,
                }
                # Get primary image
                primary_image = cart_item.product.images.filter(is_primary=True).first()
                if primary_image:
                    snapshot['primary_image'] = primary_image.image.url if primary_image.image else None
                item_name = cart_item.product.name
            
            elif cart_item.item_type == 'style' and cart_item.style:
                snapshot = {
                    'id': str(cart_item.style.id),
                    'name': cart_item.style.name,
                    'slug': cart_item.style.slug,
                    'description': cart_item.style.description,
                    'base_price': str(cart_item.style.base_price),
                    'gender': cart_item.style.gender,
                    'is_customizable': cart_item.style.is_customizable,
                    'estimated_making_time': cart_item.style.estimated_making_time,
                    'category_name': cart_item.style.category.name if cart_item.style.category else None,
                    'video_link': cart_item.style.video_link,
                }
                primary_image = cart_item.style.images.filter(is_primary=True).first()
                if primary_image:
                    snapshot['primary_image'] = primary_image.image.url if primary_image.image else None
                item_name = cart_item.style.name
            
            elif cart_item.item_type == 'appointment' and cart_item.appointment:
                snapshot = {
                    'id': str(cart_item.appointment.id),
                    'appointment_type': cart_item.appointment.appointment_type,
                    'tier': cart_item.appointment.tier.name if cart_item.appointment.tier else None,
                    'tier_fee': str(cart_item.appointment.tier.fee) if cart_item.appointment.tier else None,
                    'slot_date': str(cart_item.appointment.slot.date) if cart_item.appointment.slot else None,
                    'status': cart_item.appointment.status,
                }
                item_name = f"Appointment - {cart_item.appointment.get_appointment_type_display()}"
            
            elif cart_item.item_type == 'custom':
                snapshot = {
                    'name': cart_item.custom_name,
                    'description': cart_item.custom_description,
                    'fabric': cart_item.custom_fabric,
                    'notes': cart_item.custom_notes,
                }
                item_name = cart_item.custom_name or "Custom Order"
            
            # Add person and measurement data if present
            person_name = ''
            measurement_data = None
            if cart_item.person:
                person_name = cart_item.person.name
                snapshot['person'] = {
                    'id': str(cart_item.person.id),
                    'name': cart_item.person.name,
                    'relationship': cart_item.person.relationship,
                }
            if cart_item.measurement:
                measurement_data = cart_item.measurement.data
                snapshot['measurement'] = {
                    'id': str(cart_item.measurement.id),
                    'data': cart_item.measurement.data,
                    'notes': cart_item.measurement.notes,
                }
            
            # Create order item
            OrderItem.objects.create(
                order=order,
                item_type=cart_item.item_type,
                snapshot=snapshot,
                item_name=item_name,
                quantity=cart_item.quantity,
                price=cart_item.price,
                person_name=person_name,
                measurement_data=measurement_data,
                production_stage='pending'
            )
        
        # Create order history entry
        OrderHistory.objects.create(
            order=order,
            old_status='pending',
            new_status='pending',
            note='Order created',
            changed_by=user
        )
        
        # Clear cart
        cart.clear()
        
        return order


class OrderUpdateStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    note = serializers.CharField(required=False, allow_blank=True)
    
    def validate_status(self, value):
        order = self.context['order']
        if value == order.status:
            raise serializers.ValidationError(f"Order is already in {value} status.")
        return value


class ProductionStageUpdateSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=OrderItem.PRODUCTION_STAGE_CHOICES)
    note = serializers.CharField(required=False, allow_blank=True)
    
    def validate_stage(self, value):
        order_item = self.context['order_item']
        if value == order_item.production_stage:
            raise serializers.ValidationError(f"Already in {value} stage.")
        return value


class TransactionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'order', 'user', 'appointment', 'transaction_type', 
                  'payment_method', 'amount', 'currency', 'reference', 
                  'gateway_reference', 'status', 'status_display', 
                  'payment_method_display', 'gateway_response', 'metadata',
                  'created_at', 'completed_at']
        read_only_fields = ['id', 'created_at']


class InitializePaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField(required=False)
    appointment_id = serializers.UUIDField(required=False)
    schedule_id = serializers.UUIDField(required=False)
    payment_method = serializers.ChoiceField(choices=Transaction.PAYMENT_METHOD_CHOICES, default='paystack')
    
    def validate(self, data):
        order_id = data.get('order_id')
        appointment_id = data.get('appointment_id')
        
        schedule_id = data.get('schedule_id')
        if not order_id and not appointment_id and not schedule_id:
            raise serializers.ValidationError("Either order_id or appointment_id is required.")
        
        if sum(bool(value) for value in (order_id, appointment_id, schedule_id)) > 1:
            raise serializers.ValidationError("Provide either order_id or appointment_id, not both.")
        
        return data


class PaymentScheduleSerializer(serializers.ModelSerializer):
    effective_due_date = serializers.DateField(read_only=True)

    class Meta:
        model = PaymentSchedule
        fields = ['id', 'label', 'amount', 'due_date', 'effective_due_date', 'grace_days',
                  'sequence', 'status', 'paid_at', 'admin_note']


class VerifyPaymentSerializer(serializers.Serializer):
    reference = serializers.CharField(required=True)
    
    def validate_reference(self, value):
        if not value:
            raise serializers.ValidationError("Reference is required.")
        return value


class OrderHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderHistory
        fields = ['id', 'order', 'old_status', 'new_status', 'note', 
                  'changed_by', 'changed_by_name', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return f"{obj.changed_by.first_name} {obj.changed_by.last_name}".strip() or obj.changed_by.username
        return None


class ProductionStageHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductionStageHistory
        fields = ['id', 'order_item', 'old_stage', 'new_stage', 'note', 
                  'changed_by', 'changed_by_name', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return f"{obj.changed_by.first_name} {obj.changed_by.last_name}".strip() or obj.changed_by.username
        return None


# orders/webhook_serializers.py
class WebhookPayloadSerializer(serializers.Serializer):
    """Validate webhook payload from Paystack"""
    event = serializers.CharField()
    data = serializers.JSONField()
    
    def validate_event(self, value):
        valid_events = ['charge.success', 'charge.failed', 'transfer.success', 'transfer.failed']
        if value not in valid_events:
            raise serializers.ValidationError(f"Unsupported event: {value}")
        return value
    
    def get_transaction_reference(self):
        """Extract transaction reference from validated data"""
        return self.validated_data['data'].get('reference')
    
    def get_transaction_amount(self):
        """Extract amount from validated data (in kobo/pesewas)"""
        return self.validated_data['data'].get('amount')
    
    def is_successful(self):
        """Check if charge was successful"""
        event = self.validated_data['event']
        data = self.validated_data['data']
        
        if event == 'charge.success':
            return data.get('status') == 'success'
        return False
