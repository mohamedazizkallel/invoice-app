from django.db import models
from django.utils import timezone
from django.template.defaultfilters import slugify
from uuid import uuid4
from django.contrib.auth.models import User

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
        
class Product(models.Model):
    CURRENCY = [
        ('TND', 'Tunisian Dinar'),
        ('$', 'USD')
    ]

    title = models.CharField(null=True, blank=True, max_length=200)
    currency = models.CharField(choices=CURRENCY, default='TND', max_length=200)
    description = models.TextField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)
    quantity = models.IntegerField(null=True, blank=True)

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '{}{}'.format(self.title, self.uniqueId)

    def get_absolute_url(self):
        return reversed('product-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        
        if self.date_created is None:
            self.date_created = now
        
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]

        # Generate a unique slug using title + uniqueId
        if not self.slug:
            base_slug = slugify(self.title or "product")
            self.slug = f"{base_slug}-{self.uniqueId}"

        self.last_updated = now
        super(Product, self).save(*args, **kwargs)


class InvoiceProduct(models.Model):
    """Intermediate model to track products in invoices with specific quantities"""
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='invoice_products')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1, help_text="Quantity of this product in the invoice")
    unit_price = models.FloatField(help_text="Price at the time of invoice creation")
    
    class Meta:
        unique_together = ('invoice', 'product')
        verbose_name = "Invoice Product"
        verbose_name_plural = "Invoice Products"
    
    def __str__(self):
        return f"{self.product.title} x {self.quantity} in {self.invoice.uniqueId}"
    
    def get_line_total(self):
        """Calculate line total (quantity × unit price)"""
        from decimal import Decimal
        return Decimal(str(self.unit_price)) * Decimal(str(self.quantity))
    
    def save(self, *args, **kwargs):
        # Store the current price when adding product to invoice
        if not self.unit_price:
            self.unit_price = self.product.price
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
    product = models.ManyToManyField('Product', through='InvoiceProduct', blank=True)
    
    # NEW FIELDS - Add these to your existing model
    inventory_adjusted = models.BooleanField(default=False, help_text="Has inventory been deducted?")
    tva = models.DecimalField(max_digits=5, decimal_places=2, default=19.00, help_text="TVA percentage", null=True, blank=True)
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=3, default=1.000, help_text="Timbre fiscal amount (D)", null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Discount percentage", null=True, blank=True)

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} {self.uniqueId}"

    def get_absolute_url(self):
        return reversed('invoice-detail', kwargs={'slug': self.slug})
    
    def adjust_inventory(self):
        """Deduct invoice quantities from product inventory"""
        if self.inventory_adjusted:
            return False  # Already adjusted
        
        for invoice_product in self.invoice_products.all():
            product = invoice_product.product
            if product.quantity >= invoice_product.quantity:
                product.quantity -= invoice_product.quantity
                product.save()
            else:
                # Not enough stock
                return False
        
        self.inventory_adjusted = True
        self.save()
        return True
    
    def restore_inventory(self):
        """Restore inventory when invoice is deleted or reversed"""
        if not self.inventory_adjusted:
            return False
        
        for invoice_product in self.invoice_products.all():
            product = invoice_product.product
            product.quantity += invoice_product.quantity
            product.save()
        
        self.inventory_adjusted = False
        self.save()
        return True
    
    def calculate_subtotal(self):
        """Calculate subtotal (before TVA and fees)"""
        from decimal import Decimal
        subtotal = Decimal('0')
        for invoice_product in self.invoice_products.all():
            subtotal += invoice_product.get_line_total()
        return subtotal
    
    def calculate_discount_amount(self):
        """Calculate discount amount"""
        from decimal import Decimal
        if self.discount:
            return (self.calculate_subtotal() * self.discount) / Decimal('100')
        return Decimal('0')
    
    def calculate_subtotal_after_discount(self):
        """Calculate subtotal after discount"""
        return self.calculate_subtotal() - self.calculate_discount_amount()
    
    def calculate_tva_amount(self):
        """Calculate TVA amount"""
        from decimal import Decimal
        if self.tva:
            return (self.calculate_subtotal_after_discount() * self.tva) / Decimal('100')
        return Decimal('0')
    
    def calculate_total(self):
        """Calculate final total (subtotal - discount + TVA + timbre fiscal)"""
        from decimal import Decimal
        subtotal = self.calculate_subtotal()
        discount_amount = self.calculate_discount_amount()
        tva_amount = self.calculate_tva_amount()
        timbre = self.timbre_fiscal or Decimal('0')
        
        total = subtotal - discount_amount + tva_amount + timbre
        return total

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
        if not self.uniqueId:
            self.uniqueId = str(uuid4()).split('-')[4]
        if not self.slug:
            base_slug = slugify(self.title or "invoice")
            self.slug = f"{base_slug}-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Restore inventory before deleting invoice
        self.restore_inventory()
        super().delete(*args, **kwargs)

class Settings(models.Model):
    clientname = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.ImageField(default='default_logo.jpg', upload_to='company_logos')
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    adress = models.CharField(null=True, blank=True, max_length=200)
    mf = models.CharField(null=True, blank=True, max_length=100)
    dt = models.FloatField(null=True, blank=True)
    tva = models.IntegerField(null=True, blank=True)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)


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
