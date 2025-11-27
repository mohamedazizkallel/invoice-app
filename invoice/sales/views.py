from django.contrib.auth.decorators import login_required,user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .forms import ClientForm, InvoiceForm,ProductForm, UserLoginForm
from .models import Product,Client,Invoice,Settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,logout,login as auth_login
from random import randint
from uuid import uuid4


def anonymous_required(function=None, redirect_url=None):
    if not redirect_url:
        redirect_url="dashboard"

    actual_decorator = user_passes_test(
        lambda u: u.is_anonymous,
        login_url=redirect_url
    )

    if function:
        return actual_decorator(function)
    return actual_decorator

@anonymous_required
def login_view(request):  # changed name
    context = {}

    if request.method == 'GET':
        form = UserLoginForm()
        context['form'] = form
        return render(request, 'sales/login.html', context)

    if request.method == 'POST':
        form = UserLoginForm(request.POST)

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)  # use Django's login
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid Credentials')
            return render(request, 'sales/login.html', {'form': form})
def logout_view(request):
    logout(request)
    return redirect('index')

def index(request):
    context = {}
    return render(request,'sales/index.html',context)

@login_required
def dashboard(request):
    context = {}
    return render(request,"sales/dashboard.html", context)

@login_required
def invoices(request):
    context = {}
    return render(request,"sales/invoices.html", context)

@login_required
def products(request):
    context = {}
    return render(request,"sales/products.html", context)

@login_required
def clients(request):
    context = {}

    # Use the model name Client, not clients
    clients_qs = Client.objects.all()
    context['clients'] = clients_qs

    if request.method == 'GET':
        form = ClientForm()
        context['form'] = form
        return render(request, 'sales/clients.html', context)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'New Client Added')
            return redirect('clients')
        else:
            messages.error(request, 'Problem processing your request')
            return redirect('clients')
        
    return render(request, 'sales/clients.html', context)
    