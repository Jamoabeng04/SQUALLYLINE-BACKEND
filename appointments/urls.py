# appointments/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    # Tiers
    path('tiers/', list_tiers, name='list-tiers'),
    path('admin/tiers/create/', create_tier, name='create-tier'),
    path('admin/tiers/<uuid:tier_id>/', manage_tier, name='manage-tier'),
    
    # Slots
    path('slots/', list_slots, name='list-slots'),
    path('slots/available/', available_slots, name='available-slots'),
    path('admin/slots/create/', create_slot, name='create-slot'),
    path('admin/slots/bulk-create/', bulk_create_slots, name='bulk-create-slots'),
    path('admin/slots/<uuid:slot_id>/', manage_slot, name='manage-slot'),
    
    # Appointments - User
    path('appointments/create/', create_appointment, name='create-appointment'),
    path('appointments/my/', my_appointments, name='my-appointments'),
    path('appointments/<uuid:appointment_id>/', appointment_detail, name='appointment-detail'),
    path('appointments/<uuid:appointment_id>/update/', update_appointment, name='update-appointment'),
    path('appointments/<uuid:appointment_id>/cancel/', cancel_appointment, name='cancel-appointment'),
    path('appointments/<uuid:appointment_id>/history/', appointment_history, name='appointment-history'),
    path('appointments/<uuid:appointment_id>/proposals/', customer_proposals, name='customer-proposals'),
    path('proposals/<uuid:proposal_id>/accept/', accept_proposal, name='accept-proposal'),
    path('proposals/<uuid:proposal_id>/reject/', reject_proposal, name='reject-proposal'),
    path('proposals/<uuid:proposal_id>/request-revision/', request_proposal_revision, name='request-proposal-revision'),
    
    # Appointments - Admin
    path('admin/appointments/', admin_list_appointments, name='admin-list-appointments'),
    path('admin/appointments/<uuid:appointment_id>/review/', admin_review_appointment, name='admin-review-appointment'),
    path('admin/appointments/<uuid:appointment_id>/status/', admin_update_status, name='admin-update-status'),
    path('admin/appointments/<uuid:appointment_id>/mark-paid/', admin_mark_paid, name='admin-mark-paid'),
    path('admin/appointments/<uuid:appointment_id>/proposals/', admin_proposals, name='admin-proposals'),
    path('admin/proposals/<uuid:proposal_id>/', admin_proposal_detail, name='admin-proposal-detail'),
    path('admin/proposals/<uuid:proposal_id>/send/', admin_send_proposal, name='admin-send-proposal'),
    path('admin/proposals/<uuid:proposal_id>/revise/', admin_revise_proposal, name='admin-revise-proposal'),
    path('admin/proposals/<uuid:proposal_id>/images/', admin_proposal_images, name='admin-proposal-images'),
    path('admin/proposals/<uuid:proposal_id>/images/<uuid:image_id>/', admin_proposal_image_detail, name='admin-proposal-image-detail'),
]
