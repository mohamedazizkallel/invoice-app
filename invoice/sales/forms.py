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

class InvoiceForm(forms.ModelForm):
    
    class Meta:
        model=Invoice
        fields=["title","status","notes","client","product"]

