from django.contrib import admin
from .models import Client,Product,Settings,Invoice

# Register your models here.
admin.site.register(Client)
admin.site.register(Product)
admin.site.register(Settings)
admin.site.register(Invoice)