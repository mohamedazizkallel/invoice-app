from django.db import models
from django.utils import timezone
from django.template.defaultfilters import slugify
from uuid import uuid4
from django.contrib.auth.models import User
from django.apps import apps
from decimal import Decimal



class Client(models.Model):
    clientname = models.CharField(null=True, blank=True, max_length=200)
    emailAddress = models.CharField(null=True, blank=True, max_length=100)
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    adress = models.CharField(null=True, blank=True, max_length=200)
    mf = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.clientname} {self.uniqueId}"

    def save(self, *args, **kwargs):

        # Set creation timestamp only first time
        if not self.date_created:
            self.date_created = timezone.localtime(timezone.now())

        # Generate unique id if missing
        if not self.uniqueId:
            self.uniqueId = str(uuid4()).split('-')[4]

        # Create slug based on name + unique id
        base_slug = slugify(f"{self.clientname}-{self.uniqueId}")
        slug = base_slug
        counter = 1

        # Ensure slug is unique
        while Client.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        self.slug = slug
        self.last_updated = timezone.localtime(timezone.now())

        super().save(*args, **kwargs)
        
class Invoice(models.Model):
    STATUS = [
        ('CURRENT','CURRENT'),
        ('OVERDUE','OVERDUE'),
        ('PAID','PAID')
    ]

    title = models.CharField(null=True, blank=True, max_length=200)
    status = models.CharField(choices=STATUS, default="CURRENT", max_length=100)
    notes = models.TextField(null=True, blank=True)

    client = models.ForeignKey('Client', blank=True, null=True, on_delete=models.SET_NULL)
    service = models.ManyToManyField('Service', through='InvoiceService', blank=True)
    
    # These will default to Settings values but can be overridden per invoice
    tva = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="TVA percentage (overrides Settings if set)")
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, help_text="Timbre fiscal amount (overrides Settings if set)")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Discount percentage", null=True, blank=True)

    is_locked = models.BooleanField(default=False)
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} {self.uniqueId}"

    def get_absolute_url(self):
        return reversed('invoice-detail', kwargs={'slug': self.slug})
    
    def get_tva(self):
        """Get TVA from invoice or fallback to Settings"""
        if self.tva is not None:
            return self.tva
        
        # Get from Settings
        settings = Settings.objects.first()
        if settings and settings.tva is not None:
            return Decimal(str(settings.tva))
        
        return Decimal('19.00')  # Default fallback
    
    def get_timbre_fiscal(self):
        """Get Timbre Fiscal from invoice or fallback to Settings"""
        if self.timbre_fiscal is not None:
            return self.timbre_fiscal
        
        # Get from Settings (dt field)
        settings = Settings.objects.first()
        if settings and settings.dt is not None:
            return Decimal(str(settings.dt))
        
        return Decimal('1.000')  # Default fallback
    
    def calculate_service_subtotal(self):
        """Calculate subtotal for all invoice items (services) before discount"""
        subtotal = Decimal('0')

        # Sum services
        for item in self.invoice_services.all():
            subtotal += item.get_line_total()

        return subtotal

    def calculate_discount_amount(self):
        """Calculate discount on combined subtotal"""
        subtotal = self.calculate_service_subtotal()
        if self.discount:
            return (subtotal * Decimal(str(self.discount))) / Decimal('100')
        return Decimal('0')

    def calculate_subtotal_after_discount(self):
        """Subtotal after discount, before TVA and timbre fiscal"""
        return self.calculate_service_subtotal() - self.calculate_discount_amount()

    def calculate_tva_amount(self):
        """Calculate TVA based on subtotal after discount"""
        subtotal_after_discount = self.calculate_subtotal_after_discount()
        tva_rate = self.get_tva()  # Use getter method
        if tva_rate:
            return (subtotal_after_discount * tva_rate) / Decimal('100')
        return Decimal('0')

    def calculate_total_tva(self):
        """Final total: subtotal - discount + TVA + timbre fiscal"""
        subtotal_after_discount = self.calculate_subtotal_after_discount()
        tva_amount = self.calculate_tva_amount()


        total = subtotal_after_discount + tva_amount 
        return total
    
    def calculate_total(self):
        timbre = self.get_timbre_fiscal() 
        tva_total = self.calculate_total_tva()
        total = tva_total + timbre
        return total

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        
        # Auto-populate from Settings if not set
        if self.tva is None or self.timbre_fiscal is None:
            settings = Settings.objects.first()
            if settings:
                if self.tva is None and settings.tva is not None:
                    self.tva = Decimal(str(settings.tva))
                if self.timbre_fiscal is None and settings.dt is not None:
                    self.timbre_fiscal = Decimal(str(settings.dt))
        
        if not self.date_created:
            self.date_created = now
        
        # Generate sequential invoice number: NUMBER-YEAR (resets annually)
        if not self.uniqueId:
            year = str(now.year)  # 2025
            
            # Find the highest invoice number for this year
            # Example: "001-2025", "002-2025"
            suffix = f"-{year}"
            
            # Get all invoices from this year
            existing_invoices = Invoice.objects.filter(
                uniqueId__endswith=suffix
            ).order_by('-uniqueId')
            
            if existing_invoices.exists():
                # Extract the number from the last invoice
                last_id = existing_invoices.first().uniqueId
                last_number = int(last_id.split('-')[0])
                next_number = last_number + 1
            else:
                # First invoice of this year
                next_number = 1
            
            # Format: 001-2025, 002-2025, etc.
            self.uniqueId = f"{str(next_number).zfill(3)}-{year}"

        if not self.slug:
            base_slug = slugify(self.title or "invoice")
            self.slug = f"{base_slug}-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Restore inventory before deleting invoice
        super().delete(*args, **kwargs)



class Settings(models.Model):
    clientname = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.ImageField(default='default_logo.jpg', upload_to='company_logos')
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    adress = models.CharField(null=True, blank=True, max_length=200)
    mf = models.CharField(null=True, blank=True, max_length=100)
    
    # dt = Timbre Fiscal (Droit de Timbre)
    dt = models.DecimalField(max_digits=10, decimal_places=3, default=1.000, null=True, blank=True, help_text="Default Timbre Fiscal")
    tva = models.DecimalField(max_digits=5, decimal_places=2, default=19.00, null=True, blank=True, help_text="Default TVA percentage")
    
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Settings"
        verbose_name_plural = "Settings"

    def __str__(self):
        return f"{self.clientname} {self.uniqueId}"

    def get_absolute_url(self):
        return reversed('settings-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
        if not self.uniqueId:
            self.uniqueId = str(uuid4()).split('-')[4]
        if not self.slug:
            base_slug = slugify(self.clientname or "settings")
            self.slug = f"{base_slug}-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)

class Service(models.Model):
    CURRENCY = [
        ('TND', 'Tunisian Dinar'),
        ('$', 'USD'),
        ('€', 'Euro')
    ]

    BILLING_TYPES = [
        ('flat', 'Flat Rate'),
        ('day', 'Per Day'),
        ('hour', 'Per Hour')
    ]

    title = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    billing_type = models.CharField(max_length=50, choices=BILLING_TYPES, default='flat')
    price = models.FloatField(null=True, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    duration_hours = models.PositiveIntegerField(null=True, blank=True)
    
    currency = models.CharField(max_length=10, choices=CURRENCY, default='TND')

    uniqueId = models.CharField(max_length=100, null=True, blank=True)
    slug = models.SlugField(max_length=500, unique=True, null=True, blank=True)
    date_created = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.uniqueId})"

    @property
    def total_price(self):
        if self.billing_type == 'flat':
            return self.price
        elif self.billing_type == 'day':
            return self.price * (self.duration_days or 1)
        elif self.billing_type == 'hour':
            return self.price * (self.duration_hours or 1)
        return self.price or 0

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())

        if not self.date_created:
            self.date_created = now

        if not self.uniqueId:
            self.uniqueId = uuid4().hex[:8]

        if not self.slug:
            self.slug = f"{slugify(self.title)}-{self.uniqueId}"

        self.last_updated = now
        super(Service, self).save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('service-detail', kwargs={'slug': self.slug})

class InvoiceService(models.Model):
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='invoice_services')
    service = models.ForeignKey('Service', on_delete=models.PROTECT)

    # these fields represent usage AT BILLING time, not in the service definition
    hours_used = models.PositiveIntegerField(null=True, blank=True)
    days_used = models.PositiveIntegerField(null=True, blank=True)

    # snapshot of price at the time of invoice creation
    unit_price = models.FloatField(help_text="Service rate at invoice time")

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.service.price  # snapshot pricing
        super().save(*args, **kwargs)

    def get_line_total(self):
        if self.service.billing_type == 'flat':
            return Decimal(str(self.unit_price))

        elif self.service.billing_type == 'hour':
            return Decimal(str(self.unit_price)) * (self.hours_used or 1)

        elif self.service.billing_type == 'day':
            return Decimal(str(self.unit_price)) * (self.days_used or 1)

        return Decimal(str(self.unit_price))
