from django.contrib import admin
from .models import Client,Settings,Invoice

# Register your models here.
admin.site.register(Client)
admin.site.register(Settings)
admin.site.register(Invoice)