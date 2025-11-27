from django.shortcuts import render
from django.contrib.auth.decorators import login_required,user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .forms import ClientForm, InvoiceForm,ProductForm
from .models import Product,Client,Invoice,Settings
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from random import randint
from uuid import uuid4


def index(request):
    context = {}
    return render(request,'sales/index.html',context)

