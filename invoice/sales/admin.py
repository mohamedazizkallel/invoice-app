from django.contrib import admin

# sales models live in tenant schemas — registering them on the shared
# admin site causes "cannot resolve related model" errors when the admin
# runs in the public schema (e.g. when creating a new tenant).
# Manage tenant data through the app UI instead.
