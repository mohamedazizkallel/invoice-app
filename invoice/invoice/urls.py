from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from tenants.views import switch_schema

urlpatterns = [
    path('admin/', admin.site.urls),
    path('switch-schema/', switch_schema, name='switch_schema'),
    path('', include('sales.urls')),
    path('payment/', include('payment.urls')),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
