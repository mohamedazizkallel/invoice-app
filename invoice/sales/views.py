from django.contrib.auth.decorators import login_required,user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q,Sum, Count
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO
from django.conf import settings
from datetime import datetime
from .forms import ClientForm, InvoiceForm,ProductForm, UserLoginForm, SettingsForm
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
def companysettings(request):
    settings_qs = Settings.objects.all()
    if request.method == "POST":
        form = SettingsForm(request.POST,request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request,"Settings Added")
            return redirect("settings")
        else:
            messages.error(request,"Problem processing your request")
            return redirect("settings")
    form = SettingsForm()
    return render(request, 'sales/settings.html', {'settings': settings_qs, 'form': form})

@login_required
def delete_settings(request, pk):
    settings = get_object_or_404(Settings, pk=pk)
    settings.delete()
    messages.success(request, "Settings removed successfully")
    return redirect('settings')

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


@login_required
def invoices_list(request):
    """Display all invoices with filtering and search"""
    invoices = Invoice.objects.all().select_related('client').prefetch_related('product')
    
    # Search filter
    search_query = request.GET.get('search', '')
    if search_query:
        invoices = invoices.filter(
            Q(title__icontains=search_query) | 
            Q(client__clientname__icontains=search_query) |
            Q(notes__icontains=search_query) |
            Q(uniqueId__icontains=search_query)
        )
    
    # Status filter
    status = request.GET.get('status', '')
    if status:
        invoices = invoices.filter(status=status)
    
    # Client filter
    client_id = request.GET.get('client', '')
    if client_id:
        invoices = invoices.filter(client_id=client_id)
    
    # Date filter
    date_from = request.GET.get('date_from', '')
    if date_from:
        invoices = invoices.filter(date_created__gte=date_from)
    
    # Sorting
    sort_by = request.GET.get('sort', '-date_created')
    invoices = invoices.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(invoices, 20)  # 20 invoices per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all clients and products for dropdowns
    clients = Client.objects.all().order_by('clientname')
    products = Product.objects.all().order_by('title')
    
    # Calculate statistics
    total_invoices = invoices.count()
    current_invoices = invoices.filter(status='CURRENT').count()
    overdue_invoices = invoices.filter(status='OVERDUE').count()
    paid_invoices = invoices.filter(status='PAID').count()
    
    context = {
        'invoices': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'clients': clients,
        'products': products,
        'form': InvoiceForm(),
        'total_invoices': total_invoices,
        'current_invoices': current_invoices,
        'overdue_invoices': overdue_invoices,
        'paid_invoices': paid_invoices,
    }
    
    return render(request, 'sales/invoices.html', context)

@login_required
def invoice_create(request):
    """Create a new invoice"""
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            # The save method in the model will automatically set date_created, uniqueId, and slug
            invoice.save()
            messages.success(request, f'Invoice "{invoice.title}" created successfully! (ID: {invoice.uniqueId})')
            return redirect('invoices_list')
        else:
            messages.error(request, 'Please correct the errors below.')
            # Return with errors
            invoices = Invoice.objects.all().order_by('-date_created')
            clients = Client.objects.all().order_by('clientName')
            products = Product.objects.all().order_by('title')
            settings = Settings.objects.all()
            context = {
                'invoices': invoices,
                'settings': settings,
                'clients': clients,
                'products': products,
                'form': form,
            }
            return render(request, 'sales/invoices.html', context)
    
    return redirect('invoices_list')

@login_required
def invoice_detail(request, invoice_id):
    """View invoice details"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    products = invoice.product.all()  # Get all products from ManyToMany
    
    # Calculate total amount and prepare products with line totals
    invoice_total = 0
    invoice_currency = 'TND'
    products_with_totals = []
    
    for product in products:
        line_total = 0
        if product.price and product.quantity:
            line_total = product.price * product.quantity
            invoice_total += line_total
            # Use the first product's currency
            if not invoice_currency or invoice_currency == 'TND':
                invoice_currency = product.currency or 'TND'
        
        # Add line total to product data
        products_with_totals.append({
            'product': product,
            'line_total': line_total
        })
    
    # Get all clients and products for the edit modal
    clients = Client.objects.all().order_by('clientname')
    all_products = Product.objects.all().order_by('title')
    
    # Get settings for company info
    try:
        from .models import Settings
        p_settings = Settings.objects.first()
    except Exception as e:
        p_settings = None
    
    context = {
        'invoice': invoice,
        'products': products,  # Original queryset for edit modal
        'products_with_totals': products_with_totals,  # Products with calculated line totals
        'invoiceTotal': invoice_total,
        'invoiceCurrency': invoice_currency,
        'clients': clients,
        'all_products': all_products,
        'p_settings': p_settings,
    }
    
    return render(request, 'sales/invoice_detail.html', context)


@login_required
def invoice_edit(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)

    if request.method == 'POST':

        title = request.POST.get('title')
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        client_id = request.POST.get('client')
        product_ids = request.POST.getlist('product')

        # Capture where the user came from
        next_url = request.POST.get('next') or reverse('invoices_list')

        try:
            if title:
                invoice.title = title
            if status:
                invoice.status = status

            invoice.notes = notes

            if client_id:
                invoice.client_id = client_id

            invoice.save()

            # Update ManyToMany field
            invoice.product.set(product_ids)

            messages.success(request, f'Invoice "{invoice.title}" updated successfully!')

        except Exception as e:
            messages.error(request, f"Error updating invoice: {str(e)}")

        # --- Safe Redirect ---
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)

        return redirect('invoices_list')

    return redirect('invoices_list')

@login_required
def invoice_delete(request, invoice_id):
    """Delete an invoice"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.method == 'POST':
        invoice_title = invoice.title
        invoice.delete()
        messages.success(request, f'Invoice "{invoice_title}" deleted successfully!')
    
    return redirect('invoices_list')


@login_required
def export_invoices(request):
    """Export all invoices to Excel"""
    invoices = Invoice.objects.all().select_related('client', 'product').order_by('-date_created')
    
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    
    # Define headers
    headers = ['Invoice ID', 'Unique ID', 'Title', 'Client', 'Product', 'Status', 'Date Created', 'Last Updated', 'Notes']
    ws.append(headers)
    
    # Style the header row
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Add invoice data
    for invoice in invoices:
        ws.append([
            invoice.id,
            invoice.uniqueId if invoice.uniqueId else '',
            invoice.title if invoice.title else '',
            invoice.client.clientName if invoice.client else 'No Client',
            invoice.product.title if invoice.product else 'No Product',
            invoice.status,
            invoice.date_created.strftime('%Y-%m-%d %H:%M') if invoice.date_created else '',
            invoice.last_updated.strftime('%Y-%m-%d %H:%M') if invoice.last_updated else '',
            invoice.notes if invoice.notes else '',
        ])
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 30
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 25
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 18
    ws.column_dimensions['H'].width = 18
    ws.column_dimensions['I'].width = 40
    
    # Save to response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=invoices_export.xlsx'
    
    wb.save(response)
    return response


@login_required
def download_invoice_template(request):
    """Download an Excel template for importing invoices"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices Template"
    
    # Define headers
    headers = ['Title', 'Client Name', 'Product Title', 'Status', 'Notes']
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
        'Sample Invoice 1',
        'Sample Client',
        'Sample Product',
        'CURRENT',
        'This is a sample invoice note'
    ])
    ws.append([
        'Sample Invoice 2',
        'Another Client',
        'Another Product',
        'PAID',
        'Another sample note'
    ])
    
    # Add instructions
    ws_instructions = wb.create_sheet("Instructions")
    instructions = [
        ['Invoice Import Template - Instructions'],
        [''],
        ['Required Columns:'],
        ['1. Title - Invoice title (required)'],
        ['2. Client Name - Exact client name from your system (required)'],
        ['3. Product Title - Exact product title from your system'],
        ['4. Status - Invoice status: CURRENT, PAID, or OVERDUE'],
        ['5. Notes - Additional notes or comments'],
        [''],
        ['Important Notes:'],
        ['- Do not modify the header row'],
        ['- Title and Client Name are required'],
        ['- Client Name must match exactly with existing clients'],
        ['- Product Title must match exactly with existing products'],
        ['- Status values are case-sensitive (use UPPERCASE)'],
        ['- Default status is CURRENT if not specified'],
        ['- Unique ID and slug will be auto-generated'],
    ]
    
    for row in instructions:
        ws_instructions.append(row)
    
    ws_instructions.column_dimensions['A'].width = 60
    ws_instructions['A1'].font = Font(bold=True, size=14)
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 40
    
    # Save to response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=invoice_import_template.xlsx'
    
    wb.save(response)
    return response


@login_required
def import_invoices(request):
    """Import invoices from Excel file"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        update_existing = request.POST.get('update_existing') == 'on'
        
        if not excel_file:
            messages.error(request, 'Please select an Excel file to upload.')
            return redirect('invoices_list')
        
        # Validate file extension
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'Invalid file format. Please upload an Excel file (.xlsx or .xls).')
            return redirect('invoices_list')
        
        # Validate file size (5MB limit)
        if excel_file.size > 5 * 1024 * 1024:
            messages.error(request, 'File size exceeds 5MB limit.')
            return redirect('invoices_list')
        
        try:
            # Load workbook
            wb = load_workbook(excel_file)
            ws = wb.active
            
            # Get headers
            headers = [cell.value for cell in ws[1]]
            
            # Validate required columns
            required_columns = ['Title', 'Client Name']
            for col in required_columns:
                if col not in headers:
                    messages.error(request, f'Missing required column: {col}')
                    return redirect('invoices_list')
            
            # Get column indices
            title_idx = headers.index('Title')
            client_name_idx = headers.index('Client Name')
            product_title_idx = headers.index('Product Title') if 'Product Title' in headers else None
            status_idx = headers.index('Status') if 'Status' in headers else None
            notes_idx = headers.index('Notes') if 'Notes' in headers else None
            
            # Process rows
            created_count = 0
            updated_count = 0
            error_count = 0
            
            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    # Get values
                    title = row[title_idx]
                    client_name = row[client_name_idx]
                    
                    # Skip empty rows
                    if not title or not client_name:
                        continue
                    
                    # Get or validate client
                    try:
                        client = Client.objects.get(clientName=client_name)
                    except Client.DoesNotExist:
                        error_count += 1
                        print(f"Row {row_num}: Client '{client_name}' not found")
                        continue
                    
                    # Get product if specified
                    product = None
                    if product_title_idx is not None and row[product_title_idx]:
                        try:
                            product = Product.objects.get(title=row[product_title_idx])
                        except Product.DoesNotExist:
                            print(f"Row {row_num}: Product '{row[product_title_idx]}' not found, skipping product")
                    
                    status = row[status_idx] if status_idx is not None and row[status_idx] else 'CURRENT'
                    notes = row[notes_idx] if notes_idx is not None and row[notes_idx] else ''
                    
                    # Validate status
                    if status not in ['CURRENT', 'OVERDUE', 'PAID']:
                        status = 'CURRENT'
                    
                    # Create or update invoice
                    if update_existing:
                        invoice, created = Invoice.objects.get_or_create(
                            title=title,
                            defaults={
                                'client': client,
                                'product': product,
                                'status': status,
                                'notes': notes,
                            }
                        )
                        
                        if not created:
                            invoice.client = client
                            invoice.product = product
                            invoice.status = status
                            invoice.notes = notes
                            invoice.save()
                            updated_count += 1
                        else:
                            created_count += 1
                    else:
                        invoice = Invoice.objects.create(
                            title=title,
                            client=client,
                            product=product,
                            status=status,
                            notes=notes,
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
                    msg_parts.append(f'{created_count} invoice(s) created')
                if updated_count > 0:
                    msg_parts.append(f'{updated_count} invoice(s) updated')
                
                success_msg = ' and '.join(msg_parts) + ' successfully!'
                messages.success(request, success_msg)
                
                if error_count > 0:
                    messages.warning(request, f'{error_count} row(s) had errors and were skipped.')
            else:
                if error_count > 0:
                    messages.error(request, f'Import failed. {error_count} row(s) had errors.')
                else:
                    messages.warning(request, 'No invoices were imported. Please check your file.')
                    
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('invoices_list')
    
    return redirect('invoices_list')