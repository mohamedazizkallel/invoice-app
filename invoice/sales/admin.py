# Tenant models are browsed via pgAdmin (schema-level access).
# Registering them here causes issues with django-tenants' TenantSyncRouter
# when the admin runs in the public schema context.
