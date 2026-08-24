from django.shortcuts import render

# Create your views here.
# appointments/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.files.base import ContentFile
from squallyline.permissions import IsAdminRole, IsStaffRole
from .models import AppointmentTier, AppointmentSlot, Appointment, AppointmentHistory, AppointmentProposal, ProposalEvent, ProposalReferenceImage
from .serializers import (
    AppointmentTierSerializer, AppointmentSlotSerializer,
    AppointmentListSerializer, AppointmentDetailSerializer,
    CreateAppointmentSerializer, UpdateAppointmentSerializer,
    AdminReviewAppointmentSerializer, AppointmentHistorySerializer,
    AvailableSlotsSerializer, ProposalSerializer, ProposalEventSerializer, ProposalReferenceImageSerializer
)
from orders.models import Order, OrderItem, PaymentSchedule


# ========== HELPER FUNCTIONS ==========

def paginate_queryset(request, queryset, serializer_class, per_page=20):
    page = request.query_params.get('page', 1)
    per_page = int(request.query_params.get('per_page', per_page))
    
    if per_page > 100:
        per_page = 100
    
    paginator = Paginator(queryset, per_page)
    
    try:
        paginated = paginator.page(page)
    except PageNotAnInteger:
        paginated = paginator.page(1)
    except EmptyPage:
        paginated = paginator.page(paginator.num_pages)
    
    serializer = serializer_class(paginated, many=True, context={'request': request})
    
    return {
        'count': paginator.count,
        'total_pages': paginator.num_pages,
        'current_page': paginated.number,
        'per_page': per_page,
        'results': serializer.data
    }


# ========== TIER VIEWS ==========

@api_view(['GET'])
@permission_classes([AllowAny])
def list_tiers(request):
    """List all active appointment tiers"""
    tiers = AppointmentTier.objects.filter(is_active=True)
    serializer = AppointmentTierSerializer(tiers, many=True)
    return Response({
        'status': 'success',
        'count': tiers.count(),
        'tiers': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminRole])
def create_tier(request):
    """Admin: Create appointment tier"""
    serializer = AppointmentTierSerializer(data=request.data)
    if serializer.is_valid():
        tier = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Tier created successfully',
            'tier': AppointmentTierSerializer(tier).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAdminRole])
def manage_tier(request, tier_id):
    """Admin: Update or delete tier"""
    tier = get_object_or_404(AppointmentTier, id=tier_id)
    
    if request.method == 'DELETE':
        tier.delete()
        return Response({
            'status': 'success',
            'message': 'Tier deleted successfully'
        }, status=status.HTTP_200_OK)
    
    serializer = AppointmentTierSerializer(
        tier,
        data=request.data,
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        updated = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Tier updated successfully',
            'tier': AppointmentTierSerializer(updated).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


# ========== SLOT VIEWS ==========

@api_view(['GET'])
@permission_classes([AllowAny])
def list_slots(request):
    """List available slots with optional date filtering"""
    slots = AppointmentSlot.objects.filter(is_active=True)
    
    # Filter by date range
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if start_date:
        slots = slots.filter(date__gte=start_date)
    if end_date:
        slots = slots.filter(date__lte=end_date)
    
    # Only show future slots
    slots = slots.filter(date__gte=timezone.now().date())
    
    slots = slots.order_by('date', 'start_time')
    
    # Check if user wants availability info
    include_availability = request.query_params.get('include_availability', 'false').lower() == 'true'
    
    serializer = AppointmentSlotSerializer(slots, many=True)
    
    return Response({
        'status': 'success',
        'count': slots.count(),
        'slots': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def available_slots(request):
    """Get available slots with booking counts"""
    date = request.query_params.get('date')
    tier = request.query_params.get('tier', 'normal')
    
    if not date:
        return Response({
            'status': 'error',
            'message': 'Date parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    slots = AppointmentSlot.objects.filter(
        date=date,
        is_active=True
    ).order_by('start_time')
    
    # Filter slots based on tier availability
    if tier == 'express':
        slots = slots.filter(express_slots__gt=0)
    else:
        slots = slots.filter(normal_slots__gt=0)
    
    serializer = AppointmentSlotSerializer(slots, many=True)
    
    return Response({
        'status': 'success',
        'date': date,
        'tier': tier,
        'count': slots.count(),
        'slots': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminRole])
def create_slot(request):
    """Admin: Create appointment slot"""
    serializer = AppointmentSlotSerializer(data=request.data)
    if serializer.is_valid():
        slot = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Slot created successfully',
            'slot': AppointmentSlotSerializer(slot).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAdminRole])
def manage_slot(request, slot_id):
    """Admin: Update or delete slot"""
    slot = get_object_or_404(AppointmentSlot, id=slot_id)
    
    if request.method == 'DELETE':
        slot.delete()
        return Response({
            'status': 'success',
            'message': 'Slot deleted successfully'
        }, status=status.HTTP_200_OK)
    
    serializer = AppointmentSlotSerializer(
        slot,
        data=request.data,
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        updated = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Slot updated successfully',
            'slot': AppointmentSlotSerializer(updated).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAdminRole])
def bulk_create_slots(request):
    """Admin: Create multiple slots at once"""
    slots_data = request.data.get('slots', [])
    
    if not slots_data:
        return Response({
            'status': 'error',
            'message': 'Slots data is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    created = []
    errors = []
    
    for data in slots_data:
        serializer = AppointmentSlotSerializer(data=data)
        if serializer.is_valid():
            slot = serializer.save()
            created.append(AppointmentSlotSerializer(slot).data)
        else:
            errors.append({
                'data': data,
                'errors': serializer.errors
            })
    
    return Response({
        'status': 'success',
        'message': f'Created {len(created)} slots, {len(errors)} failed',
        'created': created,
        'errors': errors
    }, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)


# ========== APPOINTMENT VIEWS ==========

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_appointment(request):
    """Create a new appointment"""
    serializer = CreateAppointmentSerializer(
        data=request.data,
        context={'request': request}
    )
    if serializer.is_valid():
        appointment = serializer.save()
        
        # Create history entry
        AppointmentHistory.objects.create(
            appointment=appointment,
            old_status='pending',
            new_status='pending',
            note='Appointment created',
            changed_by=request.user
        )
        
        return Response({
            'status': 'success',
            'message': 'Appointment created successfully',
            'appointment': AppointmentDetailSerializer(appointment).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_appointments(request):
    """Get appointments for the current user"""
    appointments = Appointment.objects.filter(user=request.user)
    
    # Filter by status
    status_filter = request.query_params.get('status')
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    
    # Filter by type
    type_filter = request.query_params.get('type')
    if type_filter:
        appointments = appointments.filter(appointment_type=type_filter)
    
    appointments = appointments.select_related('slot', 'tier', 'style', 'person', 'measurement')
    appointments = appointments.order_by('-created_at')
    
    return Response(paginate_queryset(request, appointments, AppointmentListSerializer))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_detail(request, appointment_id):
    """Get appointment details"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check permission
    user = request.user
    if user.role not in ['admin', 'apprentice'] and appointment.user != user:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to view this appointment'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = AppointmentDetailSerializer(appointment)
    return Response({
        'status': 'success',
        'appointment': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_appointment(request, appointment_id):
    """User: Update their pending appointment"""
    appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    
    # Only allow updates if pending
    if appointment.status != 'pending':
        return Response({
            'status': 'error',
            'message': f'Cannot update appointment with status: {appointment.get_status_display()}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = UpdateAppointmentSerializer(
        appointment,
        data=request.data,
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        updated = serializer.save()
        
        AppointmentHistory.objects.create(
            appointment=appointment,
            old_status=appointment.status,
            new_status=appointment.status,
            note='Appointment updated by user',
            changed_by=request.user
        )
        
        return Response({
            'status': 'success',
            'message': 'Appointment updated successfully',
            'appointment': AppointmentDetailSerializer(updated).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_appointment(request, appointment_id):
    """User: Cancel their appointment"""
    appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    
    # Only allow cancellation if pending or confirmed
    if appointment.status not in ['pending', 'confirmed']:
        return Response({
            'status': 'error',
            'message': f'Cannot cancel appointment with status: {appointment.get_status_display()}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    old_status = appointment.status
    appointment.status = 'cancelled'
    appointment.save()
    
    AppointmentHistory.objects.create(
        appointment=appointment,
        old_status=old_status,
        new_status='cancelled',
        note='Appointment cancelled by user',
        changed_by=request.user
    )
    
    return Response({
        'status': 'success',
        'message': 'Appointment cancelled successfully'
    }, status=status.HTTP_200_OK)


# ========== ADMIN APPOINTMENT VIEWS ==========

@api_view(['GET'])
@permission_classes([IsStaffRole])
def admin_list_appointments(request):
    """Admin: List all appointments with filters"""
    appointments = Appointment.objects.select_related('slot', 'tier', 'style', 'person', 'measurement', 'user')
    
    # Filters
    status_filter = request.query_params.get('status')
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    
    date_from = request.query_params.get('date_from')
    if date_from:
        appointments = appointments.filter(slot__date__gte=date_from)
    
    date_to = request.query_params.get('date_to')
    if date_to:
        appointments = appointments.filter(slot__date__lte=date_to)
    
    tier = request.query_params.get('tier')
    if tier:
        appointments = appointments.filter(tier__name=tier)
    
    search = request.query_params.get('search')
    if search:
        appointments = appointments.filter(
            Q(user__email__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    
    appointments = appointments.order_by('-created_at')
    
    return Response(paginate_queryset(request, appointments, AppointmentListSerializer))


@api_view(['POST'])
@permission_classes([IsAdminRole])
def admin_review_appointment(request, appointment_id):
    """Admin: Review and set price/status for appointment"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Only allow review if pending
    if appointment.status != 'pending':
        return Response({
            'status': 'error',
            'message': f'Cannot review appointment with status: {appointment.get_status_display()}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = AdminReviewAppointmentSerializer(data=request.data)
    if serializer.is_valid():
        old_status = appointment.status
        new_status = serializer.validated_data['status']
        
        appointment.final_price = serializer.validated_data['final_price']
        appointment.estimated_completion_date = serializer.validated_data['estimated_completion_date']
        appointment.admin_notes = serializer.validated_data.get('admin_notes', '')
        appointment.status = new_status
        appointment.save()
        
        AppointmentHistory.objects.create(
            appointment=appointment,
            old_status=old_status,
            new_status=new_status,
            note=f'Admin review: {serializer.validated_data.get("admin_notes", "Reviewed by admin")}',
            changed_by=request.user
        )
        
        return Response({
            'status': 'success',
            'message': f'Appointment {new_status} successfully',
            'appointment': AppointmentDetailSerializer(appointment).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsStaffRole])
def admin_update_status(request, appointment_id):
    """Admin: Update appointment status"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    new_status = request.data.get('status')
    note = request.data.get('note', '')
    
    if not new_status:
        return Response({
            'status': 'error',
            'message': 'Status is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if new_status not in dict(Appointment.STATUS_CHOICES):
        return Response({
            'status': 'error',
            'message': 'Invalid status'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    old_status = appointment.status
    appointment.status = new_status
    appointment.save()
    
    AppointmentHistory.objects.create(
        appointment=appointment,
        old_status=old_status,
        new_status=new_status,
        note=note or f'Status updated by admin',
        changed_by=request.user
    )
    
    return Response({
        'status': 'success',
        'message': f'Appointment status updated to {appointment.get_status_display()}',
        'appointment': AppointmentDetailSerializer(appointment).data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_proposals(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    proposals = appointment.proposals.exclude(status='draft')
    return Response({'status': 'success', 'proposals': ProposalSerializer(proposals, many=True).data})


@api_view(['GET', 'POST'])
@permission_classes([IsStaffRole])
def admin_proposals(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    if request.method == 'GET':
        return Response({'status': 'success', 'proposals': ProposalSerializer(appointment.proposals.all(), many=True).data})
    serializer = ProposalSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    version = (appointment.proposals.order_by('-version').values_list('version', flat=True).first() or 0) + 1
    proposal = serializer.save(appointment=appointment, version=version, created_by=request.user, status='draft')
    ProposalEvent.objects.create(proposal=proposal, event='created', actor=request.user)
    return Response({'status': 'success', 'proposal': ProposalSerializer(proposal).data}, status=201)


@api_view(['GET', 'PATCH'])
@permission_classes([IsStaffRole])
def admin_proposal_detail(request, proposal_id):
    proposal = get_object_or_404(AppointmentProposal, id=proposal_id)
    if request.method == 'GET':
        return Response({'status': 'success', 'proposal': ProposalSerializer(proposal).data, 'events': ProposalEventSerializer(proposal.events.all(), many=True).data})
    if proposal.status != 'draft':
        return Response({'status': 'error', 'message': 'Sent proposals are immutable; create a revision.'}, status=400)
    serializer = ProposalSerializer(proposal, data=request.data, partial=True); serializer.is_valid(raise_exception=True); serializer.save()
    ProposalEvent.objects.create(proposal=proposal, event='edited', actor=request.user)
    return Response({'status': 'success', 'proposal': serializer.data})


@api_view(['POST'])
@permission_classes([IsStaffRole])
def admin_send_proposal(request, proposal_id):
    proposal = get_object_or_404(AppointmentProposal, id=proposal_id, status='draft')
    proposal.status = 'sent'; proposal.save(update_fields=['status', 'updated_at'])
    ProposalEvent.objects.create(proposal=proposal, event='sent', actor=request.user)
    return Response({'status': 'success', 'proposal': ProposalSerializer(proposal).data})


@api_view(['POST'])
@permission_classes([IsStaffRole])
def admin_revise_proposal(request, proposal_id):
    old = get_object_or_404(AppointmentProposal, id=proposal_id)
    allowed = ['garment_type','specification','customer_notes','internal_notes','total_price','payment_plan','deposit_percent','deposit_amount','deposit_due_date','balance_due_date','completion_date','expires_at']
    payload = {key: request.data.get(key, getattr(old, key)) for key in allowed}
    serializer = ProposalSerializer(data=payload); serializer.is_valid(raise_exception=True)
    version = (old.appointment.proposals.order_by('-version').values_list('version', flat=True).first() or 0) + 1
    revised = serializer.save(appointment=old.appointment, version=version, created_by=request.user, status='draft')
    for reference in old.reference_images.all():
        reference.image.open('rb')
        copy = ContentFile(reference.image.read(), name=reference.image.name.rsplit('/', 1)[-1])
        ProposalReferenceImage.objects.create(proposal=revised, image=copy, alt_text=reference.alt_text, order=reference.order)
    ProposalEvent.objects.create(proposal=revised, event='revision_created', note=f'Revised from v{old.version}', actor=request.user)
    return Response({'status': 'success', 'proposal': ProposalSerializer(revised).data}, status=201)


def _customer_proposal(proposal_id, user):
    return get_object_or_404(AppointmentProposal, id=proposal_id, appointment__user=user, status='sent')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_proposal_revision(request, proposal_id):
    proposal = _customer_proposal(proposal_id, request.user); proposal.status = 'revision_requested'; proposal.save(update_fields=['status', 'updated_at'])
    ProposalEvent.objects.create(proposal=proposal, event='revision_requested', note=request.data.get('reason', ''), actor=request.user)
    return Response({'status': 'success', 'proposal': ProposalSerializer(proposal).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_proposal(request, proposal_id):
    proposal = _customer_proposal(proposal_id, request.user); proposal.status = 'rejected'; proposal.rejected_reason = request.data.get('reason', '')
    proposal.save(update_fields=['status', 'rejected_reason', 'updated_at'])
    ProposalEvent.objects.create(proposal=proposal, event='rejected', note=proposal.rejected_reason, actor=request.user)
    return Response({'status': 'success', 'proposal': ProposalSerializer(proposal).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_proposal(request, proposal_id):
    with transaction.atomic():
        proposal = get_object_or_404(AppointmentProposal.objects.select_for_update(), id=proposal_id, appointment__user=request.user)
        if proposal.status != 'sent' or (proposal.expires_at and proposal.expires_at <= timezone.now()):
            return Response({'status': 'error', 'message': 'This proposal is no longer available.'}, status=400)
        proposal.status = 'accepted'; proposal.accepted_at = timezone.now(); proposal.save(update_fields=['status', 'accepted_at', 'updated_at'])
        appointment = proposal.appointment
        order = Order.objects.create(user=request.user, order_type='style' if appointment.style_id else 'custom', subtotal=proposal.total_price, total=proposal.total_price,
            priority={'normal':'standard','urgent':'priority','express':'express'}[appointment.tier.name], deposit_required=proposal.deposit_amount,
            balance_due_date=proposal.balance_due_date, estimated_delivery_date=proposal.completion_date, source_proposal=proposal,
            shipping_address='To be agreed', shipping_city='To be agreed', shipping_phone=appointment.contact_phone, customer_notes=proposal.customer_notes)
        OrderItem.objects.create(order=order, item_type=order.order_type, item_name=proposal.garment_type or 'Bespoke garment', quantity=appointment.quantity,
            price=proposal.total_price / max(1, appointment.quantity), person_name=str(appointment.person or ''),
            snapshot={'proposal_version': proposal.version, 'specification': proposal.specification,
                      'reference_images': [image.image.url for image in proposal.reference_images.all()]})
        PaymentSchedule.objects.create(order=order, label='Required payment before work starts', amount=proposal.deposit_amount, due_date=proposal.deposit_due_date, sequence=1)
        if proposal.balance_amount > 0:
            PaymentSchedule.objects.create(order=order, label='Remaining balance', amount=proposal.balance_amount, due_date=proposal.balance_due_date, sequence=2)
        ProposalEvent.objects.create(proposal=proposal, event='accepted_order_created', note=order.order_number, actor=request.user)
    return Response({'status': 'success', 'proposal': ProposalSerializer(proposal).data, 'order_id': order.id}, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsStaffRole])
def admin_proposal_images(request, proposal_id):
    proposal = get_object_or_404(AppointmentProposal, id=proposal_id)
    if proposal.status != 'draft' and request.method == 'POST':
        return Response({'status': 'error', 'message': 'Sent proposals are immutable; create a revision.'}, status=400)
    if request.method == 'POST':
        files = request.FILES.getlist('images') or ([request.FILES['image']] if 'image' in request.FILES else [])
        if proposal.reference_images.count() + len(files) > 10:
            return Response({'status': 'error', 'message': 'A proposal can have up to 10 reference images.'}, status=400)
        for index, upload in enumerate(files):
            ProposalReferenceImage.objects.create(proposal=proposal, image=upload, alt_text=proposal.garment_type,
                                                  order=proposal.reference_images.count() + index)
    return Response({'status': 'success', 'images': ProposalReferenceImageSerializer(proposal.reference_images.all(), many=True).data})


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsStaffRole])
def admin_proposal_image_detail(request, proposal_id, image_id):
    proposal = get_object_or_404(AppointmentProposal, id=proposal_id, status='draft')
    image = get_object_or_404(proposal.reference_images, id=image_id)
    if request.method == 'DELETE': image.delete(); return Response(status=204)
    serializer = ProposalReferenceImageSerializer(image, data=request.data, partial=True); serializer.is_valid(raise_exception=True); serializer.save()
    return Response({'status': 'success', 'image': serializer.data})


@api_view(['POST'])
@permission_classes([IsAdminRole])
def admin_mark_paid(request, appointment_id):
    """Admin: Mark appointment as paid"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    if appointment.status not in ['confirmed', 'in_progress']:
        return Response({
            'status': 'error',
            'message': f'Cannot mark as paid with status: {appointment.get_status_display()}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if appointment.is_paid:
        return Response({
            'status': 'error',
            'message': 'Appointment is already marked as paid'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    appointment.is_paid = True
    appointment.save()
    
    AppointmentHistory.objects.create(
        appointment=appointment,
        old_status=appointment.status,
        new_status=appointment.status,
        note='Payment confirmed by admin',
        changed_by=request.user
    )
    
    return Response({
        'status': 'success',
        'message': 'Appointment marked as paid',
        'appointment': AppointmentDetailSerializer(appointment).data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_history(request, appointment_id):
    """Get appointment history"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check permission
    user = request.user
    if user.role not in ['admin', 'apprentice'] and appointment.user != user:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to view this history'
        }, status=status.HTTP_403_FORBIDDEN)
    
    history = appointment.history.all().order_by('-created_at')
    serializer = AppointmentHistorySerializer(history, many=True)
    
    return Response({
        'status': 'success',
        'count': history.count(),
        'history': serializer.data
    }, status=status.HTTP_200_OK)
