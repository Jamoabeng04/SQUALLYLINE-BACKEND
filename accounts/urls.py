# accounts/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    # Auth
    path('auth/register/', register, name='register'),
    path('auth/login/', login, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/refresh/', refresh_token, name='refresh-token'),
    path('auth/me/', get_current_user, name='current-user'),
    
    # Profile
    path('profile/', update_profile, name='update-profile'),
    path('profile/change-password/', change_password, name='change-password'),
    
    # User Management (Admin/Apprentice)
    path('users/', list_users, name='list-users'),
    path('users/<uuid:user_id>/', manage_user, name='manage-user'),
    path('users/<uuid:user_id>/toggle-status/', toggle_user_status, name='toggle-user-status'),
    
    # People
    path('people/', people_list, name='people-list'),
    path('people/<uuid:person_id>/', person_detail, name='person-detail'),
    path('people/<uuid:person_id>/measurements/', person_measurements, name='person-measurements'),
    
    # Measurements
    path('measurements/', measurements_list, name='measurements-list'),
    path('measurements/<uuid:measurement_id>/', measurement_detail, name='measurement-detail'),
    path('measurements/<uuid:measurement_id>/history/', measurement_history_view, name='measurement-history'),
    path('measurements/<uuid:measurement_id>/set-active/', set_active_measurement, name='set-active-measurement'),
    
    # Dashboard
    path('dashboard/stats/', get_dashboard_stats, name='dashboard-stats'),
    path('dashboard/my-summary/', get_my_summary, name='my-summary'),
]