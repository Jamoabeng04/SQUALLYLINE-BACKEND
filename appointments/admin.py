from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(AppointmentTier)
admin.site.register(AppointmentSlot)
admin.site.register(Appointment)
admin.site.register(AppointmentHistory)