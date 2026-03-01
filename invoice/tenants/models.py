from django.db import models
from django.contrib.auth.models import User
from django_tenants.models import TenantMixin, DomainMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)
    auto_create_schema = True

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    """Required by django-tenants internally, even though we route by session."""
    pass


class TenantUser(models.Model):
    """Links a User (in public schema) to a Tenant."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_user')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='users')

    def __str__(self):
        return f"{self.user.username} → {self.tenant.name}"
