from django.db import models
from squallyline.image_utils import validate_image_upload

# Create your models here.
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('apprentice', 'Apprentice'),
        ('customer', 'Customer'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    
    email = models.EmailField(unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        
    def __str__(self):
        return self.email


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    profile_pic = models.ImageField(upload_to='profiles/', null=True, blank=True, validators=[validate_image_upload])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'profiles'
        
    def __str__(self):
        return f"{self.user.email}'s profile"


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='people')
    
    RELATIONSHIP_CHOICES = (
        ('mother', 'Mother'),
        ('father', 'Father'),
        ('sister', 'Sister'),
        ('brother', 'Brother'),
        ('friend', 'Friend'),
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('other', 'Other'),
    )
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    # Drives which measurement tutorial clip the app shows for this person.
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'people'
        unique_together = ['user', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.relationship})"


class Measurement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='measurements')
    
    data = models.JSONField()
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'measurements'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.person.name} - {self.created_at.date()}"


class MeasurementHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    measurement = models.ForeignKey(Measurement, on_delete=models.CASCADE, related_name='history')
    
    old_data = models.JSONField()
    new_data = models.JSONField()
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'measurement_history'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.measurement.person.name} - {self.created_at}"
