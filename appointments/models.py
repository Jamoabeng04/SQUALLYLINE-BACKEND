from django.db import models

# Create your models here.
# appointments/models.py
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import User, Person, Measurement
from products.models import Style
from squallyline.image_utils import validate_image_upload


class AppointmentTier(models.Model):
    """Admin configurable tiers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, choices=(
        ('normal', 'Normal'),
        ('urgent', 'Urgent'),
        ('express', 'Express'),
    ), unique=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'appointment_tiers'
        ordering = ['fee']
    
    def __str__(self):
        return f"{self.get_name_display()} - ${self.fee}"


class AppointmentSlot(models.Model):
    """Admin defined slots per date"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    normal_slots = models.PositiveIntegerField(default=3, help_text="Number of normal appointment slots")
    express_slots = models.PositiveIntegerField(default=1, help_text="Number of express slots (overrides normal)")
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'appointment_slots'
        ordering = ['date', 'start_time']
        unique_together = ['date', 'start_time', 'end_time']
    
    def __str__(self):
        return f"{self.date} {self.start_time} - {self.end_time}"
    
    @property
    def booked_normal_count(self):
        return self.appointments.filter(
            tier__name='normal',
            status__in=['pending', 'confirmed', 'in_progress']
        ).count()
    
    @property
    def booked_express_count(self):
        return self.appointments.filter(
            tier__name='express',
            status__in=['pending', 'confirmed', 'in_progress']
        ).count()
    
    @property
    def booked_urgent_count(self):
        return self.appointments.filter(
            tier__name='urgent',
            status__in=['pending', 'confirmed', 'in_progress']
        ).count()
    
    @property
    def total_booked(self):
        return self.booked_normal_count + self.booked_urgent_count + self.booked_express_count
    
    @property
    def is_fully_booked(self):
        return self.total_booked >= (self.normal_slots + self.express_slots)
    
    @property
    def is_normal_full(self):
        return self.booked_normal_count >= self.normal_slots
    
    @property
    def is_express_full(self):
        return self.booked_express_count >= self.express_slots


class Appointment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    )
    
    FABRIC_PROVIDER_CHOICES = (
        ('user', 'User Provides'),
        ('tailor', 'Tailor Provides'),
    )
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    slot = models.ForeignKey(AppointmentSlot, on_delete=models.CASCADE, related_name='appointments')
    tier = models.ForeignKey(AppointmentTier, on_delete=models.CASCADE, related_name='appointments')
    
    # Style-based (optional)
    style = models.ForeignKey(Style, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    measurement = models.ForeignKey(Measurement, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    
    # Appointment details
    appointment_type = models.CharField(max_length=50, choices=(
        ('consultation', 'Consultation'),
        ('style_order', 'Style Order'),
        ('custom_order', 'Custom Order'),
        ('fitting', 'Fitting'),
        ('other', 'Other'),
    ), default='consultation')
    
    # Style order specific fields
    fabric_provider = models.CharField(max_length=10, choices=FABRIC_PROVIDER_CHOICES, blank=True)
    fabric_type = models.CharField(max_length=100, blank=True, help_text="Type of fabric if user provides")
    quantity = models.PositiveIntegerField(default=1)
    contact_phone = models.CharField(max_length=20)
    contact_email = models.EmailField(blank=True)
    additional_notes = models.TextField(blank=True)
    
    # Admin review fields
    admin_notes = models.TextField(blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Set by admin after review")
    estimated_completion_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_paid = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'appointments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.slot.date} - {self.get_status_display()}"
    
    @property
    def is_style_order(self):
        return self.style is not None
    
    @property
    def requires_payment(self):
        """Check if payment is required based on tier"""
        return self.tier.name in ['urgent', 'express']
    
    @property
    def can_book(self):
        """Check if slot is available for this tier"""
        if self.tier.name == 'express':
            return not self.slot.is_express_full
        else:
            return not self.slot.is_normal_full


class AppointmentHistory(models.Model):
    """Track appointment status changes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='history')
    
    old_status = models.CharField(max_length=20, choices=Appointment.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=Appointment.STATUS_CHOICES)
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'appointment_history'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.appointment.id} - {self.old_status} → {self.new_status}"


class AppointmentProposal(models.Model):
    """A structured, versioned agreement produced after a consultation."""
    STATUS_CHOICES = (('draft','Draft'), ('sent','Sent to customer'), ('revision_requested','Revision requested'), ('accepted','Accepted'), ('rejected','Rejected'), ('expired','Expired'))
    PAYMENT_CHOICES = (('full','Full payment'), ('deposit_percent','Percentage deposit'), ('deposit_fixed','Fixed deposit'))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='proposals')
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default='draft')
    garment_type = models.CharField(max_length=120, blank=True)
    specification = models.JSONField(default=dict, blank=True)
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    legacy_reference_urls = models.JSONField(default=list, blank=True, editable=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_plan = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='full')
    deposit_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deposit_due_date = models.DateField(null=True, blank=True)
    balance_due_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_proposals')
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-version', '-created_at']
        unique_together = ['appointment', 'version']

    def calculate_amounts(self):
        from decimal import Decimal
        total = Decimal(self.total_price or 0)
        if self.payment_plan == 'full': self.deposit_amount = total
        elif self.payment_plan == 'deposit_percent': self.deposit_amount = (total * Decimal(self.deposit_percent or 0) / 100).quantize(Decimal('0.01'))
        self.balance_amount = max(Decimal('0'), total - self.deposit_amount)
        return self


class ProposalEvent(models.Model):
    proposal = models.ForeignKey(AppointmentProposal, on_delete=models.CASCADE, related_name='events')
    event = models.CharField(max_length=40)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ProposalReferenceImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(AppointmentProposal, on_delete=models.CASCADE, related_name='reference_images')
    image = models.ImageField(upload_to='proposal_references/', validators=[validate_image_upload])
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
    

    
