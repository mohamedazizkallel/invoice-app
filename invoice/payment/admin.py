from django.contrib import admin
from .models import Retenu, InvoiceRetenu

@admin.register(Retenu)
class RetenuAdmin(admin.ModelAdmin):
    list_display = ['subcategory', 'rate', 'category', 'is_active', 'updated_at']
    list_filter = ['category', 'is_active']
    search_fields = ['subcategory']
    ordering = ['category', 'rate']
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('category', 'subcategory', 'rate')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InvoiceRetenu)
class InvoiceRetenuAdmin(admin.ModelAdmin):
    list_display = [
        'invoice', 
        'retenu_type', 
        'base_amount', 
        'retenu_rate',
        'retenu_amount', 
        'created_at'
    ]
    list_filter = ['created_at', 'retenu_type__category']
    search_fields = ['invoice__title', 'invoice__uniqueId', 'notes']
    readonly_fields = ['retenu_amount', 'created_at', 'updated_at']
    raw_id_fields = ['invoice']
    
    fieldsets = (
        ('Facture', {
            'fields': ('invoice',)
        }),
        ('Retenue', {
            'fields': ('retenu_type', 'base_amount', 'retenu_rate', 'retenu_amount')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('invoice', 'retenu_type')