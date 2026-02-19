from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.template.defaultfilters import slugify
from uuid import uuid4
from decimal import Decimal


category = [("Person Physique","PP"),("Person Moral","PM")]

class Client(models.Model):
    clientname = models.CharField(null=True, blank=True, max_length=200)
    emailAddress = models.CharField(null=True, blank=True, max_length=100)
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    adress = models.CharField(null=True, blank=True, max_length=200)
    status = models.CharField(null=True, blank=True, choices=category,max_length=200)
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

    def get_balance(self):
        """Positive = client owes money (net debits)"""
        from django.db.models import Sum, Q
        totals = self.transactions.aggregate(
            total_debit=Sum('amount', filter=Q(transaction_type='DEBIT')),
            total_credit=Sum('amount', filter=Q(transaction_type='CREDIT'))
        )
        total_debit = totals['total_debit'] or Decimal('0')
        total_credit = totals['total_credit'] or Decimal('0')
        return total_debit - total_credit


class ClientTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]
    SOURCE_TYPES = [
        ('INVOICE_CREATED', 'Facture créée'),
        ('INVOICE_PAID', 'Facture payée'),
        ('INVOICE_DELETED', 'Facture annulée'),
        ('MANUAL', 'Saisie manuelle'),
    ]

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='transactions')
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    source = models.CharField(max_length=20, choices=SOURCE_TYPES, default='MANUAL')
    amount = models.DecimalField(max_digits=15, decimal_places=3)
    description = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"{self.client.clientname} - {self.transaction_type} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.date_created:
            self.date_created = timezone.localtime(timezone.now())
        super().save(*args, **kwargs)


class Supplier(models.Model):
    name = models.CharField(null=True, blank=True, max_length=200)
    emailAddress = models.CharField(null=True, blank=True, max_length=100)
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    adress = models.CharField(null=True, blank=True, max_length=200)
    status = models.CharField(null=True, blank=True, choices=category,max_length=200)
    mf = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} {self.uniqueId}"

    def save(self, *args, **kwargs):

        # Set creation timestamp only first time
        if not self.date_created:
            self.date_created = timezone.localtime(timezone.now())

        # Generate unique id if missing
        if not self.uniqueId:
            self.uniqueId = str(uuid4()).split('-')[4]

        # Create slug based on name + unique id
        base_slug = slugify(f"{self.name}-{self.uniqueId}")
        slug = base_slug
        counter = 1

        # Ensure slug is unique
        while Supplier.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        self.slug = slug
        self.last_updated = timezone.localtime(timezone.now())

        super().save(*args, **kwargs)

    def get_balance(self):
        """Positive = we owe supplier (net credits)"""
        from django.db.models import Sum, Q
        totals = self.supplier_transactions.aggregate(
            total_debit=Sum('amount', filter=Q(transaction_type='DEBIT')),
            total_credit=Sum('amount', filter=Q(transaction_type='CREDIT'))
        )
        total_debit = totals['total_debit'] or Decimal('0')
        total_credit = totals['total_credit'] or Decimal('0')
        return total_credit - total_debit


class SupplierTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]
    SOURCE_TYPES = [
        ('PURCHASE_CONFIRMED', 'Achat confirmé'),
        ('PURCHASE_PAID', 'Achat payé'),
        ('PURCHASE_DELETED', 'Achat annulé'),
        ('MANUAL', 'Saisie manuelle'),
    ]

    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, related_name='supplier_transactions')
    purchase = models.ForeignKey('Purchase', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    source = models.CharField(max_length=20, choices=SOURCE_TYPES, default='MANUAL')
    amount = models.DecimalField(max_digits=15, decimal_places=3)
    description = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"{self.supplier.name} - {self.transaction_type} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.date_created:
            self.date_created = timezone.localtime(timezone.now())
        super().save(*args, **kwargs)


class Supply(models.Model):
    CATEGORY_CHOICES = [
        ('raw_material', 'Matières premières'),
        ('consumable', 'Consommables'),
        ('packaging', 'Emballage'),
        ('spare_part', 'Pièces de rechange'),
        ('other', 'Autre'),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='raw_material')
    unit = models.CharField(max_length=50, default='pièce')
    unit_price = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    stock_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    min_stock = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    preferred_supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='supplies')
    apply_fodec = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    uniqueId = models.CharField(max_length=100, null=True, blank=True)
    slug = models.SlugField(max_length=500, unique=True, null=True, blank=True)
    date_created = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Fourniture"
        verbose_name_plural = "Fournitures"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.stock_quantity} {self.unit})"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.min_stock

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
        if not self.uniqueId:
            self.uniqueId = uuid4().hex[:8]
        if not self.slug:
            self.slug = f"{slugify(self.name or 'supply')}-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)


class Purchase(models.Model):
    STATUS = [
        ('DRAFT', 'Brouillon'),
        ('CONFIRMED', 'Confirmé'),
        ('RECEIVED', 'Reçu'),
        ('PAID', 'Payé'),
    ]

    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases')
    status = models.CharField(choices=STATUS, default='DRAFT', max_length=20)
    notes = models.TextField(null=True, blank=True)
    tva = models.DecimalField(max_digits=5, decimal_places=2, default=19.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=3, default=1.000)

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"Achat #{self.uniqueId} - {self.supplier}"

    def calculate_subtotal(self):
        subtotal = Decimal('0')
        for line in self.purchase_lines.all():
            subtotal += line.get_line_total()
        return subtotal

    def calculate_discount_amount(self):
        subtotal = self.calculate_subtotal()
        if self.discount:
            return (subtotal * Decimal(str(self.discount))) / Decimal('100')
        return Decimal('0')

    def calculate_subtotal_after_discount(self):
        return self.calculate_subtotal() - self.calculate_discount_amount()

    def calculate_total_fodec(self):
        return sum(line.get_fodec_amount() for line in self.purchase_lines.all())

    def calculate_tva_amount(self):
        subtotal_after_discount = self.calculate_subtotal_after_discount()
        fodec = self.calculate_total_fodec()
        if self.tva:
            return ((subtotal_after_discount + fodec) * Decimal(str(self.tva))) / Decimal('100')
        return Decimal('0')

    def calculate_total_before_timbre(self):
        """Total HT+FODEC+TVA — this is the base for retenu calculation."""
        subtotal_after_discount = self.calculate_subtotal_after_discount()
        fodec = self.calculate_total_fodec()
        tva_amount = self.calculate_tva_amount()
        return subtotal_after_discount + fodec + tva_amount

    def calculate_total(self):
        timbre = Decimal(str(self.timbre_fiscal)) if self.timbre_fiscal else Decimal('0')
        return self.calculate_total_before_timbre() + timbre

    def get_total_retenue(self):
        return sum(
            (r.retenu_amount for r in self.purchase_retenues.all()),
            Decimal('0.000')
        )

    def get_net_amount(self):
        return self.calculate_total() - self.get_total_retenue()

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
        if not self.uniqueId:
            year = str(now.year)
            suffix = f"-{year}"
            existing = Purchase.objects.filter(uniqueId__endswith=suffix).order_by('-uniqueId')
            if existing.exists():
                last_id = existing.first().uniqueId
                last_number = int(last_id.split('-')[0])
                next_number = last_number + 1
            else:
                next_number = 1
            self.uniqueId = f"{str(next_number).zfill(3)}-{year}"
        if not self.slug:
            self.slug = f"purchase-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)


class PurchaseLine(models.Model):
    purchase = models.ForeignKey('Purchase', on_delete=models.CASCADE, related_name='purchase_lines')
    supply = models.ForeignKey('Supply', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=15, decimal_places=3)
    unit_price = models.DecimalField(max_digits=15, decimal_places=3)
    has_fodec = models.BooleanField(default=False)

    def get_line_total(self):
        return self.quantity * self.unit_price

    def get_fodec_amount(self):
        if self.has_fodec:
            return self.get_line_total() * Decimal('0.01')
        return Decimal('0')

    def __str__(self):
        return f"{self.supply.name} x {self.quantity}"


class InvoiceSupplyUsage(models.Model):
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='supply_usages')
    service = models.ForeignKey('Service', on_delete=models.SET_NULL, null=True, blank=True)
    supply = models.ForeignKey('Supply', on_delete=models.PROTECT)
    quantity_used = models.DecimalField(max_digits=15, decimal_places=3)
    date_used = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.supply.name} x {self.quantity_used} for Invoice #{self.invoice.uniqueId}"

    def save(self, *args, **kwargs):
        if not self.date_used:
            self.date_used = timezone.localtime(timezone.now())
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
    amount_paid = models.DecimalField(max_digits=15, decimal_places=3, default=Decimal('0.000'), help_text="Total amount paid so far (partial or full)")

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
        """Get TVA from invoice. save() already auto-populates from Settings."""
        if self.tva is not None:
            return Decimal(str(self.tva))
        return Decimal('19.00')

    def get_timbre_fiscal(self):
        """Get Timbre Fiscal from invoice. save() already auto-populates from Settings."""
        if self.timbre_fiscal is not None:
            return Decimal(str(self.timbre_fiscal))
        return Decimal('1.000')
    
    def calculate_service_subtotal(self):
        """Calculate subtotal for all invoice services (services) before discount"""
        subtotal = Decimal('0')

        # Sum services
        for service in self.invoice_services.all():
            subtotal += service.get_line_ht()

        return subtotal

    def calculate_total_fodec(self):
        """Calculate total FODEC (1%) for all applicable invoice services"""
        total = Decimal('0')
        for service in self.invoice_services.all():
            total += service.get_fodec_amount()
        return total

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
        """Calculate TVA based on subtotal after discount + FODEC"""
        subtotal_after_discount = self.calculate_subtotal_after_discount()
        total_fodec = self.calculate_total_fodec()
        tva_rate = self.get_tva()  # Use getter method
        if tva_rate:
            return ((subtotal_after_discount + total_fodec) * tva_rate) / Decimal('100')
        return Decimal('0')

    def calculate_total_tva(self):
        """Final total: subtotal - discount + FODEC + TVA"""
        subtotal_after_discount = self.calculate_subtotal_after_discount()
        total_fodec = self.calculate_total_fodec()
        tva_amount = self.calculate_tva_amount()

        total = subtotal_after_discount + total_fodec + tva_amount
        return total
    
    def calculate_total(self):
        # Fetch invoice_services once — sub-methods would each re-query, causing 6× hits
        services = list(self.invoice_services.all())
        subtotal = sum(svc.get_line_ht() for svc in services)
        fodec = sum(svc.get_fodec_amount() for svc in services)
        discount_amount = (subtotal * Decimal(str(self.discount))) / Decimal('100') if self.discount else Decimal('0')
        subtotal_after_discount = subtotal - discount_amount
        tva_base = subtotal_after_discount + fodec
        tva = (tva_base * self.get_tva()) / Decimal('100')
        timbre = self.get_timbre_fiscal()
        return tva_base + tva + timbre
    
    def get_total_retenue(self):
        """Total retenue à la source"""
        return self.retenues.aggregate(
            total=Sum('retenu_amount')
        )['total'] or Decimal('0.000')
    
    def get_net_amount(self):
        return self.calculate_total() - self.get_total_retenue()

    
    def has_retenue(self):
        """Check if invoice has any retention"""
        return self.retenues.exists()

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
    status = models.CharField(null=True, blank=True, choices=category,max_length=200)
    mf = models.CharField(null=True, blank=True, max_length=100)
    rib = models.CharField(null=True, blank=True, max_length=100,help_text="RIB")
    
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

    CACHE_KEY = 'company_settings'

    @classmethod
    def get_cached(cls):
        from django.core.cache import cache
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj = cls.objects.first()
            cache.set(cls.CACHE_KEY, obj, timeout=None)  # no expiry — invalidated on save
        return obj

    def save(self, *args, **kwargs):
        from django.core.cache import cache
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
        cache.delete(self.CACHE_KEY)  # invalidate so next read fetches fresh data

class Service(models.Model):
    CURRENCY = [
        ('TND', 'Tunisian Dinar'),
        ('$', 'USD'),
        ('€', 'Euro')
    ]

    BILLING_TYPES = [
        ('flat', 'Flat Rate'),
        ('day', 'Per Day'),
        ('hour', 'Per Hour'),
        ('unit', 'Per Piece/Unit')
    ]
    PRODUCT_TYPES = [
        ('service', 'Service'),
        ('good', 'Physical Good'),
    ]

    title = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    billing_type = models.CharField(max_length=50, choices=BILLING_TYPES, default='flat')
    price = models.DecimalField(max_digits=20, decimal_places=3, default=0.00,null=True, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    duration_hours = models.PositiveIntegerField(null=True, blank=True)

    service_type = models.CharField(max_length=10, choices=PRODUCT_TYPES, default='service')
    apply_fodec = models.BooleanField(default=False, help_text="Check if 1% FODEC applies")

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

    # Your existing explicit usage fields
    hours_used = models.PositiveIntegerField(null=True, blank=True)
    days_used = models.PositiveIntegerField(null=True, blank=True)
    
    # New explicit field for Goods
    units_used = models.PositiveIntegerField(null=True, blank=True)

    unit_price = models.DecimalField(max_digits=15, decimal_places=3) # Strongly suggest Decimal here
    has_fodec = models.BooleanField(default=False)

    def get_line_ht(self):
        """Calculates Net Price based on the explicit usage field"""
        if self.service.billing_type == 'hour':
            return self.unit_price * (self.hours_used or 1)
        elif self.service.billing_type == 'day':
            return self.unit_price * (self.days_used or 1)
        elif self.service.billing_type == 'unit':
            return self.unit_price * (self.units_used or 1)
        return self.unit_price

    def get_fodec_amount(self):
        if self.has_fodec:
            # 1% of the Net HT
            return self.get_line_ht() * Decimal('0.01')
        return Decimal('0')

    def get_vat_base(self):
        """The crucial part: VAT is calculated on (HT + FODEC)"""
        return self.get_line_ht() + self.get_fodec_amount()