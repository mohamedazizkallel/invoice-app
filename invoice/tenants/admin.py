from django.contrib import admin
from django.db import connection
from django_tenants.utils import get_public_schema_name

from tenants.models import Tenant, Domain, TenantUser, NGSignClientAccount


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


@admin.register(NGSignClientAccount)
class NGSignClientAccountAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'status', 'org_uuid', 'last_verified_at')
    readonly_fields = ('org_uuid', 'created_at', 'last_verified_at', 'status', 'notes')
    actions = ['verify_connectivity']

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'org_jwt' in form.base_fields:
            form.base_fields['org_jwt'].widget.attrs['placeholder'] = '********'
            if obj and obj.pk:
                form.base_fields['org_jwt'].required = False
                form.base_fields['org_jwt'].help_text = 'Laisser vide pour conserver le token existant.'
        return form

    def save_model(self, request, obj, form, change):
        connection.set_schema_to_public()
        if change and not form.cleaned_data.get('org_jwt'):
            obj.org_jwt = NGSignClientAccount.objects.get(pk=obj.pk).org_jwt
        super().save_model(request, obj, form, change)

    @admin.action(description='Vérifier la connectivité NGSign')
    def verify_connectivity(self, request, queryset):
        from gov.ngsign.client import check_invoice_status
        from gov.ngsign.exceptions import NGSignAuthError, NGSignAPIError
        for account in queryset:
            try:
                check_invoice_status(account.org_jwt, 'test')
                account.status = 'ACTIVE'
                account.save()
                self.message_user(request, f"{account.tenant.name}: connectivité OK")
            except NGSignAuthError:
                account.status = 'ERROR'
                account.save()
                self.message_user(request, f"{account.tenant.name}: JWT invalide ou expiré", level='error')
            except NGSignAPIError as e:
                if '401' in str(e) or '403' in str(e):
                    account.status = 'ERROR'
                    account.save()
                    self.message_user(request, f"{account.tenant.name}: authentification échouée", level='error')
                else:
                    # Any non-auth error means the connection works
                    account.status = 'ACTIVE'
                    account.save()
                    self.message_user(request, f"{account.tenant.name}: connectivité OK")
            except Exception as e:
                self.message_user(request, f"{account.tenant.name}: erreur — {e}", level='error')
