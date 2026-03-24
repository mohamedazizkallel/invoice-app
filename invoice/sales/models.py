from django.db import models, transaction as db_transaction
from decouple import config as decouple_config, UndefinedValueError as DecoupleUndefinedValueError
from django.db.models import Sum
from django.utils import timezone
from django.template.defaultfilters import slugify
from django.conf import settings
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
        Client.invalidate_mf_cache()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        Client.invalidate_mf_cache()

    @staticmethod
    def get_mf_cache_key():
        from django.db import connection
        return f'client_mf_map_{connection.schema_name}'

    @classmethod
    def get_mf_map(cls):
        from django.core.cache import cache
        key = cls.get_mf_cache_key()
        mf_map = cache.get(key)
        if mf_map is None:
            mf_map = {}
            for c in cls.objects.exclude(mf='').exclude(mf__isnull=True).values('id', 'clientname', 'mf'):
                mf_map[c['mf'].lower()] = {'name': c['clientname'], 'id': c['id']}
            cache.set(key, mf_map, timeout=None)
        return mf_map

    @classmethod
    def invalidate_mf_cache(cls):
        from django.core.cache import cache
        cache.delete(cls.get_mf_cache_key())

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
        ('AVOIR_CREATED', 'Avoir créé'),
        ('AVOIR_DELETED', 'Avoir annulé'),
        ('MANUAL', 'Saisie manuelle'),
    ]

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='transactions')
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
    credit_note = models.ForeignKey('CreditNote', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
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
        Supplier.invalidate_mf_cache()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        Supplier.invalidate_mf_cache()

    @staticmethod
    def get_mf_cache_key():
        from django.db import connection
        return f'supplier_mf_map_{connection.schema_name}'

    @classmethod
    def get_mf_map(cls):
        from django.core.cache import cache
        key = cls.get_mf_cache_key()
        mf_map = cache.get(key)
        if mf_map is None:
            mf_map = {}
            for s in cls.objects.exclude(mf='').exclude(mf__isnull=True).values('id', 'name', 'mf'):
                mf_map[s['mf'].lower()] = {'name': s['name'], 'id': s['id']}
            cache.set(key, mf_map, timeout=None)
        return mf_map

    @classmethod
    def invalidate_mf_cache(cls):
        from django.core.cache import cache
        cache.delete(cls.get_mf_cache_key())

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

    
    def get_credit_notes_total(self):
        """Total of all credit notes linked to this invoice."""
        return sum(cn.calculate_total() for cn in self.credit_notes.all())

    def get_auto_retenu_amount(self):
        """
        Auto-compute default retenu for payment if:
          - Invoice total > 1 000 D
          - No manual InvoiceRetenu already applied
          - Settings has a default_retenu_rate set
        Base = total TTC − timbre fiscal (DT)
        """
        if self.get_total_retenue() > Decimal('0'):
            return Decimal('0')  # manual retenu applied — don't double-count
        cached = Settings.get_cached()
        if not cached or not cached.default_retenu_rate:
            return Decimal('0')
        total = self.calculate_total()
        if total <= Decimal('1000'):
            return Decimal('0')
        base = total - self.get_timbre_fiscal()
        return (base * Decimal(str(cached.default_retenu_rate))) / Decimal('100')

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
        
        # Generate sequential invoice number: FV-NUMBER-YEAR (resets annually)
        if not self.uniqueId:
            year = str(now.year)

            # Get all invoices with the FV- prefix for this year
            existing_invoices = Invoice.objects.filter(
                uniqueId__startswith='FV-',
                uniqueId__endswith=f'-{year}'
            ).order_by('-date_created')

            if existing_invoices.exists():
                last_id = existing_invoices.first().uniqueId
                try:
                    last_number = int(last_id.split('-')[1])
                except (ValueError, IndexError):
                    last_number = 0
                next_number = last_number + 1
            else:
                next_number = 1

            # Format: FV-001-2026, FV-002-2026, etc.
            self.uniqueId = f"FV-{str(next_number).zfill(3)}-{year}"

        if not self.slug:
            base_slug = slugify(self.title or "invoice")
            self.slug = f"{base_slug}-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Restore inventory before deleting invoice
        super().delete(*args, **kwargs)



class CreditNote(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='credit_notes')
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_notes')
    uniqueId = models.CharField(max_length=100, blank=True, null=True)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    description = models.TextField()
    amount_ht = models.DecimalField(max_digits=15, decimal_places=3)
    tva = models.DecimalField(max_digits=5, decimal_places=2, default=19.00)
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"Avoir {self.uniqueId} - {self.client.clientname}"

    def calculate_tva_amount(self):
        return self.amount_ht * Decimal(str(self.tva)) / Decimal('100')

    def calculate_total(self):
        return self.amount_ht + self.calculate_tva_amount()

    def save(self, *args, **kwargs):
        if not self.uniqueId:
            year = timezone.now().year
            last = CreditNote.objects.filter(
                uniqueId__startswith='AV-',
                uniqueId__endswith=f'-{year}'
            ).order_by('-date_created').first()
            if last and last.uniqueId:
                try:
                    num = int(last.uniqueId.split('-')[1]) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            self.uniqueId = f'AV-{num:03d}-{year}'
        if not self.slug:
            self.slug = slugify(self.uniqueId)
        super().save(*args, **kwargs)


class Settings(models.Model):
    clientname = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.TextField(null=True, blank=True, help_text="Base64-encoded data URL of the company logo")
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    adress = models.CharField(null=True, blank=True, max_length=200)
    status = models.CharField(null=True, blank=True, choices=category,max_length=200)
    mf = models.CharField(null=True, blank=True, max_length=100)
    rib = models.CharField(null=True, blank=True, max_length=100, help_text="RIB")
    phone = models.CharField(null=True, blank=True, max_length=50)
    emailAddress = models.EmailField(null=True, blank=True)
    
    # dt = Timbre Fiscal (Droit de Timbre)
    dt = models.DecimalField(max_digits=10, decimal_places=3, default=1.000, null=True, blank=True, help_text="Default Timbre Fiscal")
    tva = models.DecimalField(max_digits=5, decimal_places=2, default=19.00, null=True, blank=True, help_text="Default TVA percentage")
    default_retenu_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Taux de retenu à la source (%) appliqué automatiquement aux factures clients > 1 000 D"
    )
    
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

    @staticmethod
    def _cache_key():
        from django.db import connection
        return f'company_settings_{connection.schema_name}'

    @classmethod
    def get_cached(cls):
        from django.core.cache import cache
        key = cls._cache_key()
        pk = cache.get(key)
        if pk is None:
            obj = cls.objects.first()
            if obj is not None:
                cache.set(key, obj.pk, timeout=None)
            return obj
        return cls.objects.filter(pk=pk).first()

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
        cache.delete(self._cache_key())  # invalidate so next read fetches fresh data
        db_transaction.on_commit(lambda: _sync_ngsign_org(self))


def _sync_ngsign_org(settings_instance):
    """
    Called via on_commit after Settings.save().
    Creates or updates the NGSign org for the current tenant.
    All errors are caught — this never raises.
    """
    import os
    import logging
    from django.db import connection
    from gov.ngsign import client
    from gov.ngsign.exceptions import NGSignError

    logger = logging.getLogger(__name__)

    required = [
        settings_instance.clientname,
        settings_instance.emailAddress,
        settings_instance.adress,
        settings_instance.mf,
    ]
    if not all(required):
        return

    try:
        partner_jwt = decouple_config('NGSIGNE_API')
    except DecoupleUndefinedValueError:
        return

    current_schema = connection.schema_name
    try:
        connection.set_schema_to_public()
        from tenants.models import Tenant, NGSignClientAccount
        tenant = Tenant.objects.get(schema_name=current_schema)
        account, _ = NGSignClientAccount.objects.get_or_create(tenant=tenant)

        if not account.org_uuid:
            result = client.create_org(
                partner_jwt,
                settings_instance.clientname,
                settings_instance.adress,
                settings_instance.emailAddress,
            )
        else:
            result = client.update_org(
                partner_jwt,
                account.org_jwt,
                settings_instance.clientname,
                settings_instance.adress,
                settings_instance.emailAddress,
            )

        account.org_uuid = result['uuid']
        account.org_jwt = result['jwt']
        account.status = 'ACTIVE'
        account.notes = ''
        account.save()

    except Exception as e:
        logger.error(f'NGSign org sync failed for schema {current_schema}: {e}')
        try:
            if 'account' in locals():
                account.status = 'ERROR'
                account.notes = str(e)
                account.save()
        except Exception:
            pass
    finally:
        try:
            connection.set_schema(current_schema)
        except Exception:
            pass


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

class BonLivraison(models.Model):
    STATUS = [
        ('DRAFT', 'Brouillon'),
        ('SENT', 'Envoyé'),
        ('DELIVERED', 'Livré'),
    ]

    client = models.ForeignKey('Client', on_delete=models.SET_NULL, null=True, blank=True, related_name='bons_livraison')
    status = models.CharField(choices=STATUS, default='DRAFT', max_length=20)
    notes = models.TextField(null=True, blank=True)
    tva = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('19.00'))
    uniqueId = models.CharField(max_length=100, blank=True, null=True)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']
        verbose_name = "Bon de Livraison"
        verbose_name_plural = "Bons de Livraison"

    def __str__(self):
        return f"BL {self.uniqueId}"

    def calculate_total_ht(self):
        return sum((line.amount for line in self.lines.all()), Decimal('0.000'))

    def calculate_tva_amount(self):
        return (self.calculate_total_ht() * Decimal(str(self.tva))) / Decimal('100')

    def calculate_total_ttc(self):
        return self.calculate_total_ht() + self.calculate_tva_amount()

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
        if not self.uniqueId:
            year = timezone.now().year
            last = BonLivraison.objects.filter(
                uniqueId__startswith='BL-',
                uniqueId__endswith=f'-{year}'
            ).order_by('-date_created').first()
            if last and last.uniqueId:
                try:
                    num = int(last.uniqueId.split('-')[1]) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            self.uniqueId = f'BL-{num:03d}-{year}'
        if not self.slug:
            base = slugify(self.uniqueId)
            slug, n = base, 1
            while BonLivraison.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        self.last_updated = now
        super().save(*args, **kwargs)


class BonLivraisonLine(models.Model):
    bon = models.ForeignKey(BonLivraison, on_delete=models.CASCADE, related_name='lines')
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=3)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.description[:50]} – {self.amount} D"


class InvoiceService(models.Model):
    invoice = models.ForeignKey(
        'Invoice', null=True, blank=True,
        on_delete=models.CASCADE, related_name='invoice_services'
    )
    devis = models.ForeignKey(
        'Devis', null=True, blank=True,
        on_delete=models.CASCADE, related_name='devis_services'
    )
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


class Devis(models.Model):
    STATUS = [
        ('PENDING', 'PENDING'),
        ('ACCEPTED', 'ACCEPTED'),
        ('REJECTED', 'REJECTED'),
    ]

    client = models.ForeignKey('Client', blank=True, null=True, on_delete=models.SET_NULL)
    title = models.CharField(null=True, blank=True, max_length=200)
    notes = models.TextField(null=True, blank=True)
    status = models.CharField(choices=STATUS, default='PENDING', max_length=100)

    tva = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)

    converted_invoice = models.OneToOneField(
        'Invoice', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='source_devis'
    )

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, null=True, blank=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']
        verbose_name_plural = 'Devis'

    def __str__(self):
        return f"Devis {self.uniqueId} - {self.client}"

    def get_tva(self):
        if self.tva is not None:
            return Decimal(str(self.tva))
        return Decimal('19.00')

    def get_timbre_fiscal(self):
        if self.timbre_fiscal is not None:
            return Decimal(str(self.timbre_fiscal))
        return Decimal('1.000')

    def calculate_service_subtotal(self):
        return sum(s.get_line_ht() for s in self.devis_services.all())

    def calculate_total_fodec(self):
        return sum(s.get_fodec_amount() for s in self.devis_services.all())

    def calculate_discount_amount(self):
        subtotal = self.calculate_service_subtotal()
        fodec = self.calculate_total_fodec()
        if self.discount:
            return (subtotal + fodec) * Decimal(str(self.discount)) / Decimal('100')
        return Decimal('0')

    def calculate_tva_amount(self):
        subtotal = self.calculate_service_subtotal()
        fodec = self.calculate_total_fodec()
        discount = self.calculate_discount_amount()
        tva_base = subtotal + fodec - discount
        return tva_base * self.get_tva() / Decimal('100')

    def calculate_total(self):
        subtotal = self.calculate_service_subtotal()
        fodec = self.calculate_total_fodec()
        discount = self.calculate_discount_amount()
        tva = self.calculate_tva_amount()
        timbre = self.get_timbre_fiscal()
        return subtotal + fodec - discount + tva + timbre

    def convert_to_invoice(self):
        """
        Creates an Invoice from this devis.
        Copies each InvoiceService row to the new invoice — the devis keeps
        its own rows as a frozen historical record.
        Marks self as ACCEPTED and stores the link.
        """
        if self.converted_invoice:
            return self.converted_invoice

        invoice = Invoice.objects.create(
            client=self.client,
            title=self.title or '',
            notes=self.notes or '',
            tva=self.tva,
            timbre_fiscal=self.timbre_fiscal,
            discount=self.discount or 0,
        )

        for ds in self.devis_services.all():
            InvoiceService.objects.create(
                invoice=invoice,
                service=ds.service,
                hours_used=ds.hours_used,
                days_used=ds.days_used,
                units_used=ds.units_used,
                unit_price=ds.unit_price,
                has_fodec=ds.has_fodec,
            )

        self.converted_invoice = invoice
        self.status = 'ACCEPTED'
        self.save()
        return invoice

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
            settings = Settings.get_cached()
            if settings:
                if self.tva is None and settings.tva is not None:
                    self.tva = Decimal(str(settings.tva))
                if self.timbre_fiscal is None and settings.dt is not None:
                    self.timbre_fiscal = Decimal(str(settings.dt))

        if not self.uniqueId:
            year = str(now.year)
            existing = Devis.objects.filter(
                uniqueId__startswith='DV-',
                uniqueId__endswith=f'-{year}'
            ).order_by('-date_created')
            if existing.exists():
                last_id = existing.first().uniqueId
                try:
                    last_number = int(last_id.split('-')[1])
                except (ValueError, IndexError):
                    last_number = 0
                next_number = last_number + 1
            else:
                next_number = 1
            self.uniqueId = f"DV-{str(next_number).zfill(3)}-{year}"

        if not self.slug:
            base_slug = slugify(self.title or "devis")
            self.slug = f"{base_slug}-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)


class NotificationState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    gov_invoice = models.ForeignKey('gov.GovInvoice', on_delete=models.CASCADE)
    status_snapshot = models.CharField(max_length=50)
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'gov_invoice')

    def __str__(self):
        return f"NotificationState({self.user}, {self.gov_invoice_id}, read={self.is_read}, dismissed={self.is_dismissed})"