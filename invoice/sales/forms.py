from django import forms
from django.contrib.auth.models import User
from django.forms import widgets
from .models import Product,Client,Invoice,Settings
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
        
class ClientForm(forms.ModelForm):
    class Meta:
        model=Client
        fields=["clientname","adress","mf","emailAddress"]

class ProductForm(forms.ModelForm):
    class Meta:
        model=Product
        fields=["title","currency","description","price","quantity"]
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 0, 'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'class': 'form-control'}),
        }

class InvoiceForm(forms.ModelForm):
    tva = forms.DecimalField(
        label="TVA",
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )

    class Meta:
        model = Invoice
        fields = ["title", "status", "notes", "client", "product", "settings", "tva"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Editing existing invoice
        if self.instance and self.instance.pk:
            self.fields['tva'].initial = self.instance.tva
        # Creating new invoice: check if a settings instance is passed in initial
        elif kwargs.get('initial') and kwargs['initial'].get('settings'):
            setting_instance = kwargs['initial']['settings']
            self.fields['tva'].initial = setting_instance.tva


class SettingsForm(forms.ModelForm):
    class Meta:
        model=Settings
        fields=["clientname","clientLogo","adress","mf","dt","tva"]
        widgets = {
            'dt': forms.NumberInput(attrs={'min': 0, 'class': 'form-control'}),
            'tva': forms.NumberInput(attrs={'min': 0, 'class': 'form-control'}),
        }
