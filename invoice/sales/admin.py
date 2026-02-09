from django.contrib import admin
from .models import Client,Settings,Invoice,ClientTransaction

# Register your models here.
admin.site.register(Client)
admin.site.register(Settings)
admin.site.register(Invoice)
admin.site.register(ClientTransaction)