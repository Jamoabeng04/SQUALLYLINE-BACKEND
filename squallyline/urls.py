"""
URL configuration for squallyline project.

All API apps are mounted under /api/ so the frontend has a single, stable prefix.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """Simple reachability probe for the frontend / LAN devices."""
    return JsonResponse({'status': 'ok', 'service': 'squallyline-api'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),

    path('api/accounts/', include('accounts.urls')),
    path('api/shop/', include('products.urls')),
    path('api/appointments/', include('appointments.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/analytics/', include('orders.admin_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
