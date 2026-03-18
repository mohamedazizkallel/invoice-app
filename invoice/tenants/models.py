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


class NGSignClientAccount(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'PENDING'),
        ('ACTIVE', 'ACTIVE'),
        ('ERROR', 'ERROR'),
    ]

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name='ngsign_account'
    )
    org_uuid = models.CharField(max_length=100, blank=True)
    org_jwt = models.TextField(blank=True)
    signer_email = models.EmailField(blank=True, help_text="Email du compte NGSign autorisé à signer (ex: votre compte partner)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"NGSign: {self.tenant.name} [{self.status}]"
