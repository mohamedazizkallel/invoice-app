from django.contrib import admin

# payment models reference sales (tenant-app) models via ForeignKey.
# Registering them on the shared admin site causes "cannot resolve related
# model" errors when the admin runs in the public schema.
# Manage tenant data through the app UI instead.