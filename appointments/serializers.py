# appointments/serializers.py
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Q
from .models import AppointmentTier, AppointmentSlot, Appointment, AppointmentHistory, AppointmentProposal, ProposalEvent, ProposalReferenceImage
from products.serializers import StyleListSerializer
from accounts.serializers import PersonSerializer, MeasurementSerializer


class AppointmentTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentTier
        fields = ['id', 'name', 'fee', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AppointmentSlotSerializer(serializers.ModelSerializer):
    booked_normal_count = serializers.IntegerField(read_only=True)
    booked_express_count = serializers.IntegerField(read_only=True)
    booked_urgent_count = serializers.IntegerField(read_only=True)
    total_booked = serializers.IntegerField(read_only=True)
    is_fully_booked = serializers.BooleanField(read_only=True)
    is_normal_full = serializers.BooleanField(read_only=True)
    is_express_full = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = AppointmentSlot
        fields = ['id', 'date', 'start_time', 'end_time', 'normal_slots', 'express_slots',
                  'booked_normal_count', 'booked_express_count', 'booked_urgent_count',
                  'total_booked', 'is_fully_booked', 'is_normal_full', 'is_express_full',
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AppointmentListSerializer(serializers.ModelSerializer):
    tier_name = serializers.CharField(source='tier.get_name_display', read_only=True)
    tier_fee = serializers.DecimalField(source='tier.fee', read_only=True, max_digits=10, decimal_places=2)
    slot_date = serializers.DateField(source='slot.date', read_only=True)
    slot_time = serializers.SerializerMethodField()
    style_name = serializers.CharField(source='style.name', read_only=True, default=None)
    style_slug = serializers.CharField(source='style.slug', read_only=True, default=None)
    person_name = serializers.CharField(source='person.name', read_only=True, default=None)
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = ['id', 'user', 'user_name', 'slot', 'slot_date', 'slot_time', 'tier', 'tier_name',
                  'tier_fee', 'appointment_type', 'style', 'style_name', 'style_slug',
                  'person', 'person_name', 'measurement', 'fabric_provider', 'fabric_type',
                  'quantity', 'contact_phone', 'contact_email', 'additional_notes',
                  'admin_notes', 'final_price', 'estimated_completion_date',
                  'status', 'is_paid', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def get_slot_time(self, obj):
        return f"{obj.slot.start_time.strftime('%I:%M %p')} - {obj.slot.end_time.strftime('%I:%M %p')}"
    
    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username


class AppointmentDetailSerializer(AppointmentListSerializer):
    style_detail = StyleListSerializer(source='style', read_only=True)
    person_detail = PersonSerializer(source='person', read_only=True)
    measurement_detail = MeasurementSerializer(source='measurement', read_only=True)
    
    class Meta(AppointmentListSerializer.Meta):
        fields = AppointmentListSerializer.Meta.fields + ['style_detail', 'person_detail', 'measurement_detail']


class CreateAppointmentSerializer(serializers.ModelSerializer):
    slot_id = serializers.UUIDField(write_only=True)
    tier_name = serializers.ChoiceField(choices=[('normal', 'Normal'), ('urgent', 'Urgent'), ('express', 'Express')], write_only=True)
    style_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    person_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    measurement_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    
    class Meta:
        model = Appointment
        fields = ['slot_id', 'tier_name', 'appointment_type', 'style_id', 'person_id',
                  'measurement_id', 'fabric_provider', 'fabric_type', 'quantity',
                  'contact_phone', 'contact_email', 'additional_notes']
    
    def validate_slot_id(self, value):
        try:
            slot = AppointmentSlot.objects.get(id=value, is_active=True)
        except AppointmentSlot.DoesNotExist:
            raise serializers.ValidationError("Invalid slot or slot is inactive.")
        
        # Check if slot is in the future
        if slot.date < timezone.now().date():
            raise serializers.ValidationError("Cannot book appointments in the past.")
        
        return value
    
    def validate_tier_name(self, value):
        try:
            tier = AppointmentTier.objects.get(name=value, is_active=True)
        except AppointmentTier.DoesNotExist:
            raise serializers.ValidationError("Invalid tier or tier is inactive.")
        return value
    
    def validate(self, data):
        slot = AppointmentSlot.objects.get(id=data['slot_id'])
        tier_name = data['tier_name']
        
        # Check slot availability based on tier
        if tier_name == 'express':
            if slot.is_express_full:
                raise serializers.ValidationError({
                    "slot_id": "No express slots available for this time slot."
                })
        else:
            if slot.is_normal_full:
                raise serializers.ValidationError({
                    "slot_id": "No normal slots available for this time slot."
                })
        
        # If style is selected, person and measurement are required
        if data.get('style_id'):
            if not data.get('person_id'):
                raise serializers.ValidationError({
                    "person_id": "Person is required when booking a style."
                })
            if not data.get('measurement_id'):
                raise serializers.ValidationError({
                    "measurement_id": "Measurement is required when booking a style."
                })
        
        # Validate person belongs to user
        if data.get('person_id'):
            from accounts.models import Person
            try:
                person = Person.objects.get(id=data['person_id'], user=self.context['request'].user)
            except Person.DoesNotExist:
                raise serializers.ValidationError({
                    "person_id": "Person not found or does not belong to you."
                })
        
        # Validate measurement belongs to person
        if data.get('measurement_id') and data.get('person_id'):
            from accounts.models import Measurement
            try:
                measurement = Measurement.objects.get(
                    id=data['measurement_id'],
                    person_id=data['person_id']
                )
            except Measurement.DoesNotExist:
                raise serializers.ValidationError({
                    "measurement_id": "Measurement not found for this person."
                })
        
        return data
    
    def create(self, validated_data):
        user = self.context['request'].user
        # slot_id validated as a bare UUID; the FK needs the row itself.
        slot = AppointmentSlot.objects.get(id=validated_data.pop('slot_id'))
        tier_name = validated_data.pop('tier_name')
        
        # Get tier
        tier = AppointmentTier.objects.get(name=tier_name)
        
        # Get style, person, measurement if provided
        style_id = validated_data.pop('style_id', None)
        person_id = validated_data.pop('person_id', None)
        measurement_id = validated_data.pop('measurement_id', None)
        
        appointment = Appointment.objects.create(
            user=user,
            slot=slot,
            tier=tier,
            style_id=style_id,
            person_id=person_id,
            measurement_id=measurement_id,
            **validated_data
        )
        
        # Set is_paid based on tier
        if tier.name in ['urgent', 'express']:
            appointment.is_paid = False  # Payment required later
        
        appointment.save()
        
        return appointment


class UpdateAppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['appointment_type', 'fabric_provider', 'fabric_type', 'quantity',
                  'contact_phone', 'contact_email', 'additional_notes', 'admin_notes',
                  'final_price', 'estimated_completion_date']
    
    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class AdminReviewAppointmentSerializer(serializers.Serializer):
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    estimated_completion_date = serializers.DateField(required=True)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=[
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], required=True)
    
    def validate_final_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Final price must be greater than 0.")
        return value
    
    def validate_estimated_completion_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Completion date cannot be in the past.")
        return value


class ProposalReferenceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalReferenceImage
        fields = ['id', 'image', 'alt_text', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProposalSerializer(serializers.ModelSerializer):
    is_overdue = serializers.SerializerMethodField()
    reference_images = ProposalReferenceImageSerializer(many=True, read_only=True)
    class Meta:
        model = AppointmentProposal
        fields = '__all__'
        read_only_fields = ['id', 'version', 'created_by', 'accepted_at', 'created_at', 'updated_at', 'balance_amount', 'deposit_amount', 'legacy_reference_urls']
    def get_is_overdue(self, obj):
        from django.utils import timezone
        return bool(obj.balance_due_date and obj.balance_due_date < timezone.now().date() and obj.balance_amount > 0)

    def create(self, validated_data):
        proposal = super().create(validated_data)
        proposal.calculate_amounts(); proposal.save(update_fields=['deposit_amount','balance_amount'])
        return proposal

    def update(self, instance, validated_data):
        proposal = super().update(instance, validated_data)
        proposal.calculate_amounts(); proposal.save(update_fields=['deposit_amount','balance_amount','updated_at'])
        return proposal


class ProposalEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalEvent
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class AppointmentHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AppointmentHistory
        fields = ['id', 'appointment', 'old_status', 'new_status', 'note', 
                  'changed_by', 'changed_by_name', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return f"{obj.changed_by.first_name} {obj.changed_by.last_name}".strip() or obj.changed_by.username
        return None


class AvailableSlotsSerializer(serializers.Serializer):
    date = serializers.DateField()
    slots = AppointmentSlotSerializer(many=True)
