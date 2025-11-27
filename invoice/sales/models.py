from django.db import models
from django.utils import timezone
from django.template.defaultfilters import slugify
from uuid import uuid4
from django.contrib.auth.models import User

class Client(models.Model):
    clientname = models.CharField(null=True, blank=True, max_length=200)
    emailAddress = models.CharField(null=True, blank=True, max_length=100)
    uniqueId = models.CharField(null = True, blank=True,max_length=100)
    adress = models.CharField(null = True, blank=True,max_length=200)
    mf = models.CharField(null = True, blank=True,max_length=100)
    slug = models.SlugField(max_length=500,unique=True,blank=True, null=True)
    date_created = models.DateTimeField(blank=True,null=True)
    last_updated = models.DateTimeField(blank=True,null=True)

    def __str__(self):
        return '{}{}'.format(self.clientname, self.uniqueId)

    def get_absolute_url(self):
        return reversed('client-detail',kwagrs={'slug':self.slug})

    def save(self,*args,**kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('')
        
        self.slug = slugify('')
        self.last_updated = timezone.localtime(timezone.now())

        super(Client,self).save(*args,**kwargs)

class Product(models.Model):
    CURRENCY =[
        ('TND','Tunisian Dinar'),
        ('$','USD')
    ]

    title = models.CharField(null=True, blank=True, max_length=200)
    currency = models.CharField(choices=CURRENCY,default='TND',max_length=200)
    description = models.TextField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)
    quantity = models.FloatField(null=True, blank=True)

    uniqueId = models.CharField(null = True, blank=True,max_length=100)
    slug = models.SlugField(max_length=500,unique=True,blank=True, null=True)
    date_created = models.DateTimeField(blank=True,null=True)
    last_updated = models.DateTimeField(blank=True,null=True)

    def __str__(self):
        return '{}{}'.format(self.title, self.uniqueId)

    def get_absolute_url(self):
        return reversed('product-detail',kwagrs={'slug':self.slug})

    def save(self,*args,**kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('')
        
        self.slug = slugify('')
        self.last_updated = timezone.localtime(timezone.now())

        super(Product,self).save(*args,**kwargs)

class Invoice(models.Model):
    STATUS = [('CURRENT','CURRENT'),
              ('OVERDUE','OVERDUE'),
              ('PAID','PAID')]

    title = models.CharField(null=True, blank=True, max_length=200)
    status = models.CharField(choices=STATUS, default="CURRENT", max_length=100)
    notes = models.TextField(null=True, blank=True)

    client = models.ForeignKey(Client, blank=True, null=True, on_delete=models.SET_NULL)
    product = models.ForeignKey(Product, blank=True, null=True, on_delete=models.SET_NULL)

    uniqueID = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500,unique=True,null=True)
    date_created = models.DateTimeField(blank=True,null=True)
    last_updated = models.DateTimeField(blank=True,null=True)

    def __str__(self):
        return '{}{}'.format(self.title, self.uniqueId)

    def get_absolute_url(self):
        return reversed('invoice-detail',kwagrs={'slug':self.slug})

    def save(self,*args,**kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('')
        
        self.slug = slugify('')
        self.last_updated = timezone.localtime(timezone.now())

        super(Invoice,self).save(*args,**kwargs)

class Settings(models.Model):
    clientname = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.ImageField(default='default_logo.jpg', upload_to='company_logos')
    uniqueId = models.CharField(null = True, blank=True,max_length=100)
    adress = models.CharField(null = True, blank=True,max_length=200)
    mf = models.CharField(null = True, blank=True,max_length=100)
    slug = models.SlugField(max_length=500,unique=True,blank=True, null=True)
    date_created = models.DateTimeField(blank=True,null=True)
    last_updated = models.DateTimeField(blank=True,null=True)

    def __str__(self):
        return '{}{}'.format(self.clientname, self.uniqueId)

    def get_absolute_url(self):
        return reversed('settings-detail',kwagrs={'slug':self.slug})

    def save(self,*args,**kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('')
        
        self.slug = slugify('')
        self.last_updated = timezone.localtime(timezone.now())

        super(Settings,self).save(*args,**kwargs)
