from django.shortcuts import render

# Create your views here.
# accounts/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from .models import User, Profile, Person, Measurement, MeasurementHistory
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer, ProfileSerializer,
    UpdateProfileSerializer, ChangePasswordSerializer, PersonSerializer,
    MeasurementSerializer, MeasurementHistorySerializer, UserListSerializer
)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# ========== AUTH VIEWS ==========

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        tokens = get_tokens_for_user(user)
        return Response({
            'status': 'success',
            'message': 'Registration successful',
            'user': UserSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        tokens = get_tokens_for_user(user)
        return Response({
            'status': 'success',
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        logout(request)
        return Response({
            'status': 'success',
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    # AllowAny: callers reach this precisely because their access token has
    # already expired. The refresh token itself is the credential.
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({
                'status': 'error',
                'message': 'Refresh token required'
            }, status=status.HTTP_400_BAD_REQUEST)

        token = RefreshToken(refresh_token)
        return Response({
            'status': 'success',
            'access': str(token.access_token)
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)


# ========== PROFILE VIEWS ==========

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    serializer = UserSerializer(request.user)
    # Superusers created via createsuperuser have no Profile row yet.
    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile_serializer = ProfileSerializer(profile)
    return Response({
        'status': 'success',
        'user': serializer.data,
        'profile': profile_serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    # The instance matters: without it save() would route to create(), which this
    # serializer does not implement, and DRF's base class raises NotImplementedError.
    serializer = UpdateProfileSerializer(
        request.user,
        data=request.data,
        context={'user': request.user},
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Profile updated successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(
        data=request.data,
        context={'user': request.user}
    )
    if serializer.is_valid():
        serializer.save()
        return Response({
            'status': 'success',
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


# ========== USER MANAGEMENT VIEWS (Admin/Staff) ==========

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_users(request):
    user = request.user
    
    # Permission check
    if user.role not in ['admin', 'apprentice']:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to view users'
        }, status=status.HTTP_403_FORBIDDEN)
    
    users = User.objects.select_related('profile').all()
    
    # Filters
    role_filter = request.query_params.get('role')
    if role_filter:
        users = users.filter(role=role_filter)
    
    search = request.query_params.get('search')
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(profile__phone__icontains=search)
        )
    
    is_active = request.query_params.get('is_active')
    if is_active is not None:
        users = users.filter(is_active=is_active.lower() == 'true')
    
    # Ordering
    users = users.order_by('-date_joined')
    
    # Pagination
    limit = min(int(request.query_params.get('limit', 20)), 100)
    offset = int(request.query_params.get('offset', 0))
    
    total_count = users.count()
    users = users[offset:offset + limit]
    
    serializer = UserListSerializer(users, many=True)
    
    return Response({
        'status': 'success',
        'count': total_count,
        'limit': limit,
        'offset': offset,
        'users': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_user(request, user_id):
    requesting_user = request.user
    
    # Permission check
    if requesting_user.role not in ['admin', 'apprentice']:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to manage users'
        }, status=status.HTTP_403_FORBIDDEN)
    
    target_user = get_object_or_404(User, id=user_id)
    
    # Prevent self-deletion
    if request.method == 'DELETE' and target_user.id == requesting_user.id:
        return Response({
            'status': 'error',
            'message': 'You cannot delete your own account'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if request.method == 'GET':
        serializer = UserListSerializer(target_user)
        return Response({
            'status': 'success',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    if request.method == 'DELETE':
        target_user.delete()
        return Response({
            'status': 'success',
            'message': 'User deleted successfully'
        }, status=status.HTTP_200_OK)
    
    # PUT/PATCH - Update user
    serializer = UpdateProfileSerializer(
        data=request.data,
        context={'user': target_user},
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'status': 'success',
            'message': 'User updated successfully',
            'user': UserListSerializer(user).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_user_status(request, user_id):
    requesting_user = request.user
    
    if requesting_user.role != 'admin':
        return Response({
            'status': 'error',
            'message': 'Only administrators can toggle user status'
        }, status=status.HTTP_403_FORBIDDEN)
    
    target_user = get_object_or_404(User, id=user_id)
    
    if target_user.id == requesting_user.id:
        return Response({
            'status': 'error',
            'message': 'You cannot toggle your own status'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    target_user.is_active = not target_user.is_active
    target_user.save()
    
    return Response({
        'status': 'success',
        'message': f"User {'activated' if target_user.is_active else 'deactivated'} successfully",
        'is_active': target_user.is_active
    }, status=status.HTTP_200_OK)


# ========== PERSON VIEWS ==========

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def people_list(request):
    if request.method == 'GET':
        people = request.user.people.all().order_by('-created_at')
        serializer = PersonSerializer(people, many=True)
        return Response({
            'status': 'success',
            'count': people.count(),
            'people': serializer.data
        }, status=status.HTTP_200_OK)
    
    # POST
    serializer = PersonSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        person = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Person created successfully',
            'person': PersonSerializer(person).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def person_detail(request, person_id):
    person = get_object_or_404(Person, id=person_id, user=request.user)
    
    if request.method == 'GET':
        serializer = PersonSerializer(person)
        return Response({
            'status': 'success',
            'person': serializer.data
        }, status=status.HTTP_200_OK)
    
    if request.method == 'DELETE':
        person.delete()
        return Response({
            'status': 'success',
            'message': 'Person deleted successfully'
        }, status=status.HTTP_200_OK)
    
    # PUT/PATCH
    serializer = PersonSerializer(
        person,
        data=request.data,
        context={'request': request},
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        updated_person = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Person updated successfully',
            'person': PersonSerializer(updated_person).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def person_measurements(request, person_id):
    person = get_object_or_404(Person, id=person_id, user=request.user)
    measurements = person.measurements.all().order_by('-created_at')
    
    serializer = MeasurementSerializer(measurements, many=True)
    return Response({
        'status': 'success',
        'person': {
            'id': str(person.id),
            'name': person.name,
            'relationship': person.relationship
        },
        'count': measurements.count(),
        'measurements': serializer.data
    }, status=status.HTTP_200_OK)


# ========== MEASUREMENT VIEWS ==========

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def measurements_list(request):
    if request.method == 'GET':
        person_ids = request.user.people.values_list('id', flat=True)
        measurements = Measurement.objects.filter(person_id__in=person_ids).order_by('-created_at')
        
        # Filter by person
        person_id = request.query_params.get('person')
        if person_id:
            measurements = measurements.filter(person_id=person_id)
        
        # Filter active only
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            measurements = measurements.filter(is_active=is_active.lower() == 'true')
        
        serializer = MeasurementSerializer(measurements, many=True)
        return Response({
            'status': 'success',
            'count': measurements.count(),
            'measurements': serializer.data
        }, status=status.HTTP_200_OK)
    
    # POST
    serializer = MeasurementSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        measurement = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Measurement created successfully',
            'measurement': MeasurementSerializer(measurement).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def measurement_detail(request, measurement_id):
    measurement = get_object_or_404(Measurement, id=measurement_id)
    
    # Check ownership via person
    if measurement.person.user != request.user:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to access this measurement'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        serializer = MeasurementSerializer(measurement)
        return Response({
            'status': 'success',
            'measurement': serializer.data
        }, status=status.HTTP_200_OK)
    
    if request.method == 'DELETE':
        measurement.delete()
        return Response({
            'status': 'success',
            'message': 'Measurement deleted successfully'
        }, status=status.HTTP_200_OK)
    
    # PUT/PATCH
    serializer = MeasurementSerializer(
        measurement,
        data=request.data,
        context={'request': request},
        partial=(request.method == 'PATCH')
    )
    if serializer.is_valid():
        updated_measurement = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Measurement updated successfully',
            'measurement': MeasurementSerializer(updated_measurement).data
        }, status=status.HTTP_200_OK)
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def measurement_history_view(request, measurement_id):
    measurement = get_object_or_404(Measurement, id=measurement_id)
    
    if measurement.person.user != request.user:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to view this measurement history'
        }, status=status.HTTP_403_FORBIDDEN)
    
    history = measurement.history.all().order_by('-created_at')
    serializer = MeasurementHistorySerializer(history, many=True)
    
    return Response({
        'status': 'success',
        'count': history.count(),
        'history': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_active_measurement(request, measurement_id):
    measurement = get_object_or_404(Measurement, id=measurement_id)
    
    if measurement.person.user != request.user:
        return Response({
            'status': 'error',
            'message': 'You do not have permission to modify this measurement'
        }, status=status.HTTP_403_FORBIDDEN)
    
    with transaction.atomic():
        # Deactivate all measurements for this person
        Measurement.objects.filter(person=measurement.person).update(is_active=False)
        
        # Activate this measurement
        measurement.is_active = True
        measurement.save()
    
    return Response({
        'status': 'success',
        'message': f"Active measurement set for {measurement.person.name}",
        'measurement': MeasurementSerializer(measurement).data
    }, status=status.HTTP_200_OK)


# ========== DASHBOARD VIEWS ==========

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_stats(request):
    user = request.user
    
    if user.role == 'admin':
        total_users = User.objects.count()
        total_customers = User.objects.filter(role='customer').count()
        total_apprentices = User.objects.filter(role='apprentice').count()
        total_admins = User.objects.filter(role='admin').count()
        
        total_people = Person.objects.count()
        total_measurements = Measurement.objects.count()
        active_measurements = Measurement.objects.filter(is_active=True).count()
        
        return Response({
            'status': 'success',
            'role': 'admin',
            'stats': {
                'users': {
                    'total': total_users,
                    'customers': total_customers,
                    'apprentices': total_apprentices,
                    'admins': total_admins
                },
                'people': total_people,
                'measurements': {
                    'total': total_measurements,
                    'active': active_measurements
                }
            }
        }, status=status.HTTP_200_OK)
    
    elif user.role == 'apprentice':
        # Apprentices see all data but with limited access (handled in permissions)
        total_customers = User.objects.filter(role='customer').count()
        total_people = Person.objects.count()
        total_measurements = Measurement.objects.filter(is_active=True).count()
        
        return Response({
            'status': 'success',
            'role': 'apprentice',
            'stats': {
                'customers': total_customers,
                'people': total_people,
                'active_measurements': total_measurements
            }
        }, status=status.HTTP_200_OK)
    
    else:  # customer
        people_count = user.people.count()
        measurements_count = Measurement.objects.filter(
            person__user=user
        ).count()
        active_measurements = Measurement.objects.filter(
            person__user=user,
            is_active=True
        ).count()
        
        return Response({
            'status': 'success',
            'role': 'customer',
            'stats': {
                'people': people_count,
                'measurements': measurements_count,
                'active_measurements': active_measurements
            }
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_summary(request):
    """Customer summary view"""
    if request.user.role != 'customer':
        return Response({
            'status': 'error',
            'message': 'This endpoint is for customers only'
        }, status=status.HTTP_403_FORBIDDEN)
    
    user = request.user
    people = user.people.all().prefetch_related('measurements')
    
    people_data = []
    for person in people:
        measurements = person.measurements.all().order_by('-created_at')
        people_data.append({
            'id': str(person.id),
            'name': person.name,
            'relationship': person.relationship,
            'measurement_count': measurements.count(),
            'latest_measurement': MeasurementSerializer(measurements.first()).data if measurements.exists() else None
        })
    
    return Response({
        'status': 'success',
        'user': {
            'id': str(user.id),
            'name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'email': user.email
        },
        'people_count': len(people_data),
        'people': people_data
    }, status=status.HTTP_200_OK)