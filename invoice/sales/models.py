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
    quantity = models.FloatField(null=True, blank=True)

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
    product = models.ForeignKey('Product', blank=True, null=True, on_delete=models.SET_NULL)

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} {self.uniqueId}"

    def get_absolute_url(self):
        return reversed('invoice-detail', kwargs={'slug': self.slug})

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

class Settings(models.Model):
    clientname = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.ImageField(default='default_logo.jpg', upload_to='company_logos')
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    adress = models.CharField(null=True, blank=True, max_length=200)
    mf = models.CharField(null=True, blank=True, max_length=100)
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
