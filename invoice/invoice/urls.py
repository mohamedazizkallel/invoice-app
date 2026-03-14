from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from tenants.views import switch_tenant
from tenants.admin_site import TenantAwareAdminSite

# Replace default admin site with tenant-aware version
admin.site.__class__ = TenantAwareAdminSite

urlpatterns = [
    path('admin/switch-tenant/', switch_tenant, name='switch_tenant'),
    path('admin/', admin.site.urls),
    path('', include('sales.urls')),
    path('payment/', include('payment.urls')),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
