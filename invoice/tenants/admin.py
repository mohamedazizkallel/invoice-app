from django.contrib import admin
from django.db import connection
from django_tenants.utils import get_public_schema_name

from tenants.models import Tenant, Domain, TenantUser


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'schema_name', 'is_active', 'created_on')

    def save_model(self, request, obj, form, change):
        # Tenant creation/update must happen on the public schema.
        # The middleware has already set the schema to the admin's own tenant,
        # so we switch back to public before saving.
        connection.set_schema_to_public()
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        connection.set_schema_to_public()
        super().delete_model(request, obj)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant')
    list_filter = ('tenant',)
