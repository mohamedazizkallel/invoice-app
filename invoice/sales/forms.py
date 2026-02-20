from django import forms
from django.contrib.auth.models import User
from django.forms import widgets
from .models import Client,Invoice,Settings,Service, Supplier, ClientTransaction, SupplierTransaction, Supply, Purchase
import json

class DateInput(forms.DateInput):
    input_type = 'date'


class UserLoginForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        "class": "form-control",
        "placeholder": "Password",
        "id": "floatingPassword"
    }))
    
    username = forms.CharField(widget=forms.TextInput(attrs={
        "class": "form-control",
        "placeholder": "Username",
        "id": "floatingInput",
        "required": True,
        "autofocus": True
    }))

    class Meta:
        model = User
        fields = ["username", "password"]
        
class SettingsForm(forms.ModelForm):
    """Form for company settings"""

    # Handled separately in the view — converted to base64 before saving
    logo_upload = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'logoUploadInput',
        }),
        label='Logo de l\'entreprise',
        help_text='PNG, JPG ou SVG. Max 2 Mo.',
    )

    class Meta:
        model = Settings
        fields = ['clientname', 'adress', 'mf', 'tva', 'dt', 'status', 'rib']
        labels = {
            'clientname': 'Nom de l\'entreprise',
            'adress': 'Adresse',
            'mf': 'Matricule fiscal (MF)',
            'tva': 'Taxe sur la Valeur Ajoutée (TVA)',
            'dt': 'Droit de Timbre (DT)',
            'rib': 'R.I.B',
            'status': "Classification d'individu ou société",
        }
        widgets = {
            'clientname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de l\'entreprise'}),
            'adress': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Adresse de l\'entreprise'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'mf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro MF'}),
            'tva': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'TVA (%)'}),
            'rib': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'RIB'}),
            'dt': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'DT (D)'}),
        }


class InvoiceForm(forms.ModelForm):
    """Enhanced invoice form with auto-populated fields from Settings"""
    
    # Additional fields from settings (can be modified per invoice)
    tva = forms.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        required=False,
        label='TVA (%)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '19.00', 'step': '0.01'})
    )
    
    timbre_fiscal = forms.DecimalField(
        max_digits=10,
        decimal_places=3,
        required=False,
        label='Timbre Fiscal (D)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1.000', 'step': '0.001'})
    )
    
    discount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='Discount (%)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'})
    )
    
    class Meta:
        model = Invoice
        fields = ['status', 'notes', 'client', 'service']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Invoice title'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional notes'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'service': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Auto-populate from settings if creating new invoice
        if not self.instance.pk:
            try:
                settings = Settings.get_cached()
                if settings:
                    # Set default TVA (typically 19% in Tunisia)
                    self.fields['tva'].initial = 19.00
                    # Set default timbre fiscal (typically 1.000 TND in Tunisia)
                    self.fields['timbre_fiscal'].initial = 1.000
            except Settings.DoesNotExist:
                pass


class ClientForm(forms.ModelForm):
    """Form for client management"""
    class Meta:
        model = Client
        fields = ['clientname', 'emailAddress', 'adress', 'mf','status']
        widgets = {
            'clientname': forms.TextInput(attrs={'class': 'form-control'}),
            'emailAddress': forms.EmailInput(attrs={'class': 'form-control'}),
            'adress': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'mf': forms.TextInput(attrs={'class': 'form-control'}),
        }

class SupplierForm(forms.ModelForm):
    """Form for client management"""
    class Meta:
        model = Supplier
        fields = ['name', 'emailAddress', 'adress', 'mf','status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'emailAddress': forms.EmailInput(attrs={'class': 'form-control'}),
            'adress': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'mf': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ServiceForm(forms.ModelForm):
    """Form for service management"""
    class Meta:
        model = Service
        fields = ['title', 'currency','billing_type', 'description','duration_days', 'duration_hours', 'price', 'apply_fodec']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'billing_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'duration_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'apply_fodec': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class ClientTransactionForm(forms.ModelForm):
    """Form for manual credit/debit entries"""
    class Meta:
        model = ClientTransaction
        fields = ['transaction_type', 'amount', 'description']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001', 'placeholder': '0.000'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Description...'}),
        }


class SupplierTransactionForm(forms.ModelForm):
    """Form for manual supplier ledger entries"""
    class Meta:
        model = SupplierTransaction
        fields = ['transaction_type', 'amount', 'description']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001', 'placeholder': '0.000'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Description...'}),
        }


class SupplyForm(forms.ModelForm):
    """Form for supply/raw material management"""
    class Meta:
        model = Supply
        fields = ['name', 'category', 'unit', 'unit_price', 'stock_quantity', 'min_stock', 'preferred_supplier', 'apply_fodec', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la fourniture'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: kg, pièce, litre'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'placeholder': '0.000'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'placeholder': '0.000'}),
            'min_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'placeholder': '0.000'}),
            'preferred_supplier': forms.Select(attrs={'class': 'form-select'}),
            'apply_fodec': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description...'}),
        }


class PurchaseForm(forms.ModelForm):
    """Form for purchase order header"""
    class Meta:
        model = Purchase
        fields = ['supplier', 'notes', 'tva', 'discount', 'timbre_fiscal']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notes...'}),
            'tva': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '19.00'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'timbre_fiscal': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'placeholder': '1.000'}),
        }