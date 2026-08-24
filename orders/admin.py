from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(CartItem)
admin.site.register(Cart)
admin.site.register(OrderItem)
admin.site.register(Order)
admin.site.register(Transaction)
admin.site.register(ProductionStageHistory)
admin.site.register(OrderHistory)