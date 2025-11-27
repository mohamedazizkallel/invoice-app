from django.contrib.auth.decorators import login_required,user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO
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
    products_qs = Product.objects.all()
    if request.method == 'Post':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "New Product Added")
            return redirect('products')
        else:
            messages.error(request,'Problem processing your request')
            return redirect('products')
    form = ProductForm()
    return render(request,"sales/products.html", {'products': products_qs, 'form': form})

@login_required
def clients(request):
    clients_qs = Client.objects.all()
    
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'New Client Added')
            return redirect('clients')
        else:
            messages.error(request, 'Problem processing your request')
            return redirect('clients')
    
    form = ClientForm()
    return render(request, 'sales/clients.html', {'clients': clients_qs, 'form': form})


@login_required
def delete_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    client.delete()
    messages.success(request, "Client removed successfully")
    return redirect('clients')

@login_required
def products_list(request):
    """Display all products with filtering and search"""
    products = Product.objects.all()
    
    # Search filter
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Category filter (if you have categories)
    category = request.GET.get('category', '')
    if category:
        products = products.filter(category_id=category)
    
    # Sorting
    sort_by = request.GET.get('sort', 'title')
    products = products.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(products, 20)  # 20 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter dropdown (if applicable)
    # categories = Category.objects.all()
    
    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'form': ProductForm(),
        # 'categories': categories,
    }
    
    return render(request, 'sales/products.html', context)


@login_required
def add_product(request):
    """Add a single product"""
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            # Add any additional fields if needed
            # product.created_by = request.user
            product.save()
            messages.success(request, f'Product "{product.title}" added successfully!')
            return redirect('products_list')
        else:
            messages.error(request, 'Please correct the errors below.')
            # Return to the same page with errors
            products = Product.objects.all().order_by('title')
            context = {
                'products': products,
                'form': form,
            }
            return render(request, 'sales/products.html', context)
    
    return redirect('products_list')


@login_required
def edit_product(request, product_id):
    """Edit an existing product"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        # Manually handle form data
        title = request.POST.get('title')
        currency = request.POST.get('currency')
        description = request.POST.get('description')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        
        try:
            # Update product fields
            product.title = title
            product.currency = currency if currency else 'TND'
            product.description = description if description else ''
            product.price = float(price) if price else 0.0
            product.quantity = int(quantity) if quantity else 0
            
            # Validate quantity is not negative
            if product.quantity < 0:
                product.quantity = 0
            
            product.save()
            messages.success(request, f'Product "{product.title}" updated successfully!')
            
        except (ValueError, TypeError) as e:
            messages.error(request, f'Invalid data provided: {str(e)}')
    
    return redirect('products_list')


@login_required
def delete_product(request, product_id):
    """Delete a product"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product_title = product.title
        product.delete()
        messages.success(request, f'Product "{product_title}" deleted successfully!')
    
    return redirect('products_list')


@login_required
def export_products(request):
    """Export all products to Excel"""
    products = Product.objects.all().order_by('title')
    
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Products"
    
    # Define headers
    headers = ['Product ID', 'Title', 'Currency', 'Description', 'Price', 'Quantity']
    ws.append(headers)
    
    # Style the header row
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Add product data
    for product in products:
        ws.append([
            product.id,
            product.title,
            product.currency if product.currency else 'ZAR',
            product.description if product.description else '',
            float(product.price) if product.price else 0.0,
            product.quantity if product.quantity else 0,
        ])
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 50
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 12
    
    # Save to response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=products_export.xlsx'
    
    wb.save(response)
    return response


@login_required
def download_product_template(request):
    """Download an Excel template for importing products"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Products Template"
    
    # Define headers
    headers = ['Title', 'Currency', 'Description', 'Price', 'Quantity']
    ws.append(headers)
    
    # Style the header row
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Add sample data
    ws.append([
        'Sample Product 1',
        'ZAR',
        'This is a sample product description',
        100.00,
        50
    ])
    ws.append([
        'Sample Product 2',
        'USD',
        'Another sample product',
        250.00,
        30
    ])
    
    # Add instructions in a separate sheet
    ws_instructions = wb.create_sheet("Instructions")
    instructions = [
        ['Product Import Template - Instructions'],
        [''],
        ['Required Columns:'],
        ['1. Title - Product name (required)'],
        ['2. Currency - Currency code (e.g., ZAR, USD, EUR)'],
        ['3. Description - Product description'],
        ['4. Price - Product price (numeric)'],
        ['5. Quantity - Stock quantity (numeric)'],
        [''],
        ['Important Notes:'],
        ['- Do not modify the header row'],
        ['- Title is required for all products'],
        ['- Price and Quantity should be numeric values'],
        ['- Leave Description empty if not applicable'],
        ['- Default currency is ZAR if not specified'],
    ]
    
    for row in instructions:
        ws_instructions.append(row)
    
    # Style instructions
    ws_instructions.column_dimensions['A'].width = 60
    ws_instructions['A1'].font = Font(bold=True, size=14)
    
    # Adjust column widths in main sheet
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 50
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12
    
    # Save to response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=product_import_template.xlsx'
    
    wb.save(response)
    return response


@login_required
def import_products(request):
    """Import products from Excel file"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        update_existing = request.POST.get('update_existing') == 'on'
        
        if not excel_file:
            messages.error(request, 'Please select an Excel file to upload.')
            return redirect('products_list')
        
        # Validate file extension
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'Invalid file format. Please upload an Excel file (.xlsx or .xls).')
            return redirect('products_list')
        
        # Validate file size (5MB limit)
        if excel_file.size > 5 * 1024 * 1024:
            messages.error(request, 'File size exceeds 5MB limit.')
            return redirect('products_list')
        
        try:
            # Load workbook
            wb = load_workbook(excel_file)
            ws = wb.active
            
            # Get headers from first row
            headers = [cell.value for cell in ws[1]]
            
            # Validate required columns
            required_columns = ['Title']
            for col in required_columns:
                if col not in headers:
                    messages.error(request, f'Missing required column: {col}')
                    return redirect('products_list')
            
            # Get column indices
            title_idx = headers.index('Title')
            currency_idx = headers.index('Currency') if 'Currency' in headers else None
            description_idx = headers.index('Description') if 'Description' in headers else None
            price_idx = headers.index('Price') if 'Price' in headers else None
            quantity_idx = headers.index('Quantity') if 'Quantity' in headers else None
            
            # Process rows
            created_count = 0
            updated_count = 0
            error_count = 0
            
            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    # Get values
                    title = row[title_idx]
                    
                    # Skip empty rows
                    if not title:
                        continue
                    
                    currency = row[currency_idx] if currency_idx is not None and row[currency_idx] else 'ZAR'
                    description = row[description_idx] if description_idx is not None else ''
                    
                    # Handle price
                    try:
                        price = float(row[price_idx]) if price_idx is not None and row[price_idx] else 0.0
                    except (ValueError, TypeError):
                        price = 0.0
                    
                    # Handle quantity
                    try:
                        quantity = int(row[quantity_idx]) if quantity_idx is not None and row[quantity_idx] else 0
                    except (ValueError, TypeError):
                        quantity = 0
                    
                    # Check if product exists (for update)
                    if update_existing:
                        product, created = Product.objects.get_or_create(
                            title=title,
                            defaults={
                                'currency': currency,
                                'description': description,
                                'price': price,
                                'quantity': quantity,
                            }
                        )
                        
                        if not created:
                            # Update existing product
                            product.currency = currency
                            product.description = description
                            product.price = price
                            product.quantity = quantity
                            product.save()
                            updated_count += 1
                        else:
                            created_count += 1
                    else:
                        # Create new product
                        Product.objects.create(
                            title=title,
                            currency=currency,
                            description=description,
                            price=price,
                            quantity=quantity,
                        )
                        created_count += 1
                        
                except Exception as e:
                    error_count += 1
                    print(f"Error processing row {row_num}: {str(e)}")
                    continue
            
            # Success message
            if created_count > 0 or updated_count > 0:
                msg_parts = []
                if created_count > 0:
                    msg_parts.append(f'{created_count} product(s) created')
                if updated_count > 0:
                    msg_parts.append(f'{updated_count} product(s) updated')
                
                success_msg = ' and '.join(msg_parts) + ' successfully!'
                messages.success(request, success_msg)
                
                if error_count > 0:
                    messages.warning(request, f'{error_count} row(s) had errors and were skipped.')
            else:
                if error_count > 0:
                    messages.error(request, f'Import failed. {error_count} row(s) had errors.')
                else:
                    messages.warning(request, 'No products were imported. Please check your file.')
                    
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('products_list')
    
    return redirect('products_list')