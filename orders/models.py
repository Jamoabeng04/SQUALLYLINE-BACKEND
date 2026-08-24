from django.db import models

# Create your models here.
# orders/models.py
import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from accounts.models import User, Person, Measurement
from products.models import Product, Style
from appointments.models import Appointment


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'carts'
    
    def __str__(self):
        return f"{self.user.email}'s Cart"
    
    @property
    def total_items(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0
    
    @property
    def subtotal(self):
        total = Decimal('0.00')
        for item in self.items.all():
            total += item.total_price
        return total
    
    @property
    def total(self):
        return self.subtotal
    
    def clear(self):
        self.items.all().delete()


class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    
    ITEM_TYPE_CHOICES = (
        ('product', 'Product'),
        ('style', 'Style'),
        ('appointment', 'Appointment'),
        ('custom', 'Custom Order'),
    )
    
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='product')
    
    # For products
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')
    product_snapshot = models.JSONField(null=True, blank=True)  # Snapshot at add to cart
    
    # For styles
    style = models.ForeignKey(Style, on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')
    style_snapshot = models.JSONField(null=True, blank=True)
    
    # For appointments
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')
    appointment_snapshot = models.JSONField(null=True, blank=True)
    
    # For custom orders
    custom_name = models.CharField(max_length=200, blank=True)
    custom_description = models.TextField(blank=True)
    custom_fabric = models.CharField(max_length=200, blank=True)
    custom_notes = models.TextField(blank=True)
    
    # Measurements for style/custom
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True)
    person_snapshot = models.JSONField(null=True, blank=True)
    measurement = models.ForeignKey(Measurement, on_delete=models.SET_NULL, null=True, blank=True)
    measurement_snapshot = models.JSONField(null=True, blank=True)
    
    # Common fields
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.product:
            return f"{self.product.name} x {self.quantity}"
        elif self.style:
            return f"{self.style.name} x {self.quantity}"
        elif self.appointment:
            return f"Appointment {self.appointment.id} x {self.quantity}"
        else:
            return f"Custom item x {self.quantity}"
    
    @property
    def total_price(self):
        return self.price * self.quantity
    
    @property
    def item_name(self):
        if self.product:
            return self.product.name
        elif self.style:
            return self.style.name
        elif self.appointment:
            return f"Appointment - {self.appointment.get_appointment_type_display()}"
        elif self.custom_name:
            return self.custom_name
        return "Custom Item"


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partial', 'Partial'),
    )
    
    ORDER_TYPE_CHOICES = (
        ('product', 'Product Order'),
        ('style', 'Style Order'),
        ('custom', 'Custom Order'),
        ('appointment', 'Appointment Booking'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    
    # Order details
    order_number = models.CharField(max_length=50, unique=True)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='product')
    
    # Items summary
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Dates
    order_date = models.DateTimeField(auto_now_add=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    estimated_delivery_date = models.DateField(null=True, blank=True)
    
    # Shipping
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_country = models.CharField(max_length=100, default='Ghana')
    shipping_zip = models.CharField(max_length=20, blank=True)
    shipping_phone = models.CharField(max_length=20)
    
    # Billing
    billing_address = models.TextField(blank=True)
    billing_same_as_shipping = models.BooleanField(default=True)
    
    # Tracking info (for products)
    tracking_number = models.CharField(max_length=100, blank=True)
    tracking_url = models.URLField(max_length=500, blank=True)
    courier = models.CharField(max_length=100, blank=True)
    
    # Admin notes
    admin_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    source_proposal = models.OneToOneField('appointments.AppointmentProposal', on_delete=models.SET_NULL, null=True, blank=True, related_name='order')
    priority = models.CharField(max_length=20, choices=(('standard','Standard'),('priority','Priority'),('express','Express')), default='standard')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    deposit_required = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance_due_date = models.DateField(null=True, blank=True)
    tracking_locked = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_number} - {self.user.email}"
    
    def generate_order_number(self):
        prefix = 'ORD'
        date = timezone.now().strftime('%Y%m%d')
        random_part = str(uuid.uuid4().hex[:6].upper())
        return f"{prefix}-{date}-{random_part}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    @property
    def is_paid(self):
        return self.payment_status == 'paid'
    
    @property
    def can_cancel(self):
        return self.status in ['pending', 'confirmed'] and not self.is_paid
    
    @property
    def can_refund(self):
        return self.is_paid and self.status in ['cancelled', 'refunded']


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    
    ITEM_TYPE_CHOICES = (
        ('product', 'Product'),
        ('style', 'Style'),
        ('custom', 'Custom Order'),
        ('appointment', 'Appointment'),
    )
    
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='product')
    
    # Snapshot data (full copy at order time)
    snapshot = models.JSONField()  # Complete snapshot of item
    
    # Common fields
    item_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Measurements (for style/custom orders)
    person_name = models.CharField(max_length=200, blank=True)
    measurement_data = models.JSONField(null=True, blank=True)
    
    # For style orders - production tracking
    PRODUCTION_STAGE_CHOICES = (
        ('pending', 'Pending'),
        ('pattern_making', 'Pattern Making'),
        ('cutting', 'Cutting'),
        ('sewing', 'Sewing'),
        ('fitting', 'Fitting'),
        ('finishing', 'Finishing'),
        ('quality_check', 'Quality Check'),
        ('ready', 'Ready'),
        ('completed', 'Completed'),
    )
    
    production_stage = models.CharField(max_length=20, choices=PRODUCTION_STAGE_CHOICES, default='pending')
    production_notes = models.TextField(blank=True)
    
    # For product orders - simple status
    is_ready = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_items'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.item_name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        self.total_price = self.price * self.quantity
        super().save(*args, **kwargs)


class ProductionStageHistory(models.Model):
    """Track production stage changes for style orders"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='stage_history')
    
    old_stage = models.CharField(max_length=20, choices=OrderItem.PRODUCTION_STAGE_CHOICES)
    new_stage = models.CharField(max_length=20, choices=OrderItem.PRODUCTION_STAGE_CHOICES)
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'production_stage_history'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_item.item_name} - {self.old_stage} → {self.new_stage}"


class PaymentSchedule(models.Model):
    """A server-controlled instalment agreed during a consultation."""
    STATUS_CHOICES = (
        ('pending', 'Pending'), ('paid', 'Paid'), ('overdue', 'Overdue'),
        ('waived', 'Waived'), ('on_hold', 'On hold'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_schedules')
    label = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    grace_days = models.PositiveSmallIntegerField(default=0)
    sequence = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sequence', 'due_date']
        unique_together = ['order', 'sequence']

    @property
    def effective_due_date(self):
        from datetime import timedelta
        return self.due_date + timedelta(days=self.grace_days) if self.due_date else None


class Transaction(models.Model):
    """Payment transactions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    TRANSACTION_TYPE_CHOICES = (
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('partial_refund', 'Partial Refund'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('paystack', 'Paystack'),
        ('momo', 'Mobile Money'),
        ('card', 'Card'),
        ('bank', 'Bank Transfer'),
        ('cash', 'Cash'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    )
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='transactions')
    payment_schedule = models.ForeignKey(PaymentSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='payment')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='paystack')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='GHS')
    
    # Payment gateway reference
    reference = models.CharField(max_length=100, unique=True)
    gateway_reference = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Gateway response
    gateway_response = models.JSONField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(null=True, blank=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.reference} - {self.amount} {self.currency} - {self.status}"
    
    @property
    def is_successful(self):
        return self.status == 'success'


class OrderHistory(models.Model):
    """Track order status changes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    
    old_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_history'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.old_status} → {self.new_status}"
