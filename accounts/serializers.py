# accounts/serializers.py
import re
import uuid
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from .models import User, Profile, Person, Measurement, MeasurementHistory


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'role', 'first_name', 'last_name', 'full_name', 'date_joined', 'last_login', 'is_active']
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Profile
        fields = ['id', 'user', 'phone', 'address', 'date_of_birth', 'gender', 'profile_pic', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default='customer')
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password', 'confirm_password', 'role', 'phone', 'address']
    
    def validate_email(self, value):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError("Enter a valid email address.")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_username(self, value):
        if not re.match(r'^[\w.@+-]+\Z', value):
            raise serializers.ValidationError("Username can only contain letters, digits, and @/./+/-/_ characters.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value
    
    def validate_password(self, value):
        validate_password(value)
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        phone = validated_data.pop('phone', '')
        address = validated_data.pop('address', '')
        role = validated_data.pop('role', 'customer')
        
        user = User.objects.create_user(**validated_data)
        user.role = role
        user.save()
        
        Profile.objects.create(user=user, phone=phone, address=address)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            raise serializers.ValidationError("Must include email and password.")
        
        user = authenticate(email=email, password=password)
        
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        
        data['user'] = user
        return data


class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    username = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Profile.GENDER_CHOICES, required=False, allow_blank=True)
    profile_pic = serializers.ImageField(required=False)
    
    def validate_email(self, value):
        if value:
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
                raise serializers.ValidationError("Enter a valid email address.")
            if User.objects.exclude(pk=self.context['user'].pk).filter(email__iexact=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_username(self, value):
        if value:
            if not re.match(r'^[\w.@+-]+\Z', value):
                raise serializers.ValidationError("Username can only contain letters, digits, and @/./+/-/_ characters.")
            if User.objects.exclude(pk=self.context['user'].pk).filter(username__iexact=value).exists():
                raise serializers.ValidationError("A user with this username already exists.")
        return value
    
    def update(self, instance, validated_data):
        user = self.context['user']
        profile = user.profile
        
        # Update user fields
        user_fields = ['first_name', 'last_name', 'email', 'username']
        for field in user_fields:
            if field in validated_data:
                setattr(user, field, validated_data[field])
        user.save()
        
        # Update profile fields
        profile_fields = ['phone', 'address', 'date_of_birth', 'gender', 'profile_pic']
        for field in profile_fields:
            if field in validated_data:
                setattr(profile, field, validated_data[field])
        profile.save()
        
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)
    
    def validate_old_password(self, value):
        user = self.context['user']
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate_new_password(self, value):
        validate_password(value)
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        if data['old_password'] == data['new_password']:
            raise serializers.ValidationError({"new_password": "New password must be different from old password."})
        return data
    
    def save(self):
        user = self.context['user']
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class PersonSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    measurement_count = serializers.SerializerMethodField()
    latest_measurement = serializers.SerializerMethodField()
    
    class Meta:
        model = Person
        fields = ['id', 'user', 'name', 'relationship', 'gender', 'phone', 'email', 'measurement_count', 'latest_measurement', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def get_measurement_count(self, obj):
        return obj.measurements.count()
    
    def get_latest_measurement(self, obj):
        latest = obj.measurements.filter(is_active=True).first()
        if latest:
            return {
                'id': str(latest.id),
                'date': latest.created_at,
                'data': latest.data
            }
        return None
    
    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value.strip()
    
    def validate_email(self, value):
        if value and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError("Enter a valid email address.")
        return value
    
    def validate(self, data):
        # On update the instance's own row must not count as a clash, otherwise
        # PATCHing anything (phone, gender) while keeping the name would fail.
        user = self.context.get('request').user
        name = data.get('name')
        if name:
            clash = Person.objects.filter(user=user, name__iexact=name)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError({"name": "A person with this name already exists for your account."})
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class MeasurementSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_relationship = serializers.CharField(source='person.relationship', read_only=True)
    
    class Meta:
        model = Measurement
        fields = ['id', 'person', 'person_name', 'person_relationship', 'data', 'notes', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    # Core fields every garment needs, regardless of who is being measured.
    # 'bust' stays optional — it only applies to women's patterns, and requiring
    # it (or requiring waist < hips) rejects perfectly normal male measurements.
    REQUIRED_MEASUREMENTS = ['chest', 'waist', 'hips', 'shoulder', 'neck']
    OPTIONAL_MEASUREMENTS = [
        'bust', 'inseam', 'outseam', 'arm_length', 'sleeve_length', 'bicep',
        'wrist', 'thigh', 'knee', 'calf', 'ankle', 'back_width', 'front_length',
        'shoulder_to_waist', 'waist_to_knee', 'waist_to_ankle', 'height', 'weight',
    ]

    def validate_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Data must be a JSON object.")

        def as_number(field, raw):
            if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
                raise serializers.ValidationError(f"'{field}' must be a number.")
            try:
                number = float(raw)
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"'{field}' must be a number.")
            if number <= 0:
                raise serializers.ValidationError(f"'{field}' must be greater than zero.")
            if number > 400:
                raise serializers.ValidationError(f"'{field}' looks too large — check the unit (cm).")
            return number

        cleaned = {}
        for field in self.REQUIRED_MEASUREMENTS:
            if field not in value or value[field] in (None, ''):
                raise serializers.ValidationError(f"'{field}' is required.")
            cleaned[field] = as_number(field, value[field])

        for field in self.OPTIONAL_MEASUREMENTS:
            if field in value and value[field] not in (None, ''):
                cleaned[field] = as_number(field, value[field])

        # Carry through anything else the client sent (unit, tutorial notes, etc.)
        for key, raw in value.items():
            if key not in cleaned:
                cleaned[key] = raw

        return cleaned
    
    def validate(self, data):
        person = data.get('person')
        request = self.context.get('request')
        if person and request and person.user != request.user:
            raise serializers.ValidationError("You can only add measurements for your own people.")
        return data
    
    def create(self, validated_data):
        # A newly taken measurement is the one the tailor should cut from, so it
        # becomes active and any earlier set for that person steps down.
        person = validated_data['person']
        make_active = validated_data.get('is_active', True)

        if make_active:
            Measurement.objects.filter(person=person, is_active=True).update(is_active=False)
        validated_data['is_active'] = make_active

        return Measurement.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        # Save history before update
        MeasurementHistory.objects.create(
            measurement=instance,
            old_data=instance.data,
            new_data=validated_data.get('data', instance.data),
            notes=validated_data.get('notes', f'Updated on {instance.updated_at}')
        )
        
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class MeasurementHistorySerializer(serializers.ModelSerializer):
    measurement_id = serializers.UUIDField(source='measurement.id', read_only=True)
    person_name = serializers.CharField(source='measurement.person.name', read_only=True)
    
    class Meta:
        model = MeasurementHistory
        fields = ['id', 'measurement_id', 'person_name', 'old_data', 'new_data', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone = serializers.CharField(source='profile.phone', read_only=True, default='')
    address = serializers.CharField(source='profile.address', read_only=True, default='')
    profile_pic = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'role', 'full_name', 'phone', 'address', 'profile_pic', 'is_active', 'date_joined', 'last_login']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    
    def get_profile_pic(self, obj):
        if hasattr(obj, 'profile') and obj.profile and obj.profile.profile_pic:
            try:
                return obj.profile.profile_pic.url
            except ValueError:
                return None
        return None