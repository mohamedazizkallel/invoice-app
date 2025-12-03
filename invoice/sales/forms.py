from django import forms
from django.contrib.auth.models import User
from django.forms import widgets
from .models import Client,Invoice,Settings,Service
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
    class Meta:
        model = Settings
        fields = ['clientname', 'clientLogo', 'adress', 'mf','tva','dt']
        labels = {
            'clientname': 'Company Name',
            'clientLogo': 'Company Logo',
            'adress': 'Company Address',
            'mf': 'Tax Registration Number (MF)',
            'tva': 'Taxe sur la Valeur Ajoutée (TVA)',
            'dt': 'Droit de Timbre (DT)',
        }
        widgets = {
            'clientname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter company name'}),
            'adress': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter company address'}),
            'mf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter MF number'}),
            'tva': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter TVA '}),
            'dt': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter DT'}),
            'clientLogo': forms.FileInput(attrs={'class': 'form-control'}),
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
        fields = ['title', 'status', 'notes', 'client', 'service']
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
                settings = Settings.objects.first()
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
        fields = ['clientname', 'emailAddress', 'adress', 'mf']
        widgets = {
            'clientname': forms.TextInput(attrs={'class': 'form-control'}),
            'emailAddress': forms.EmailInput(attrs={'class': 'form-control'}),
            'adress': forms.TextInput(attrs={'class': 'form-control'}),
            'mf': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ServiceForm(forms.ModelForm):
    """Form for service management"""
    class Meta:
        model = Service
        fields = ['title', 'currency','billing_type', 'description','duration_days', 'duration_hours', 'price']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'billing_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'duration_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'})
        }