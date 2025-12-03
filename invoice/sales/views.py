from django.contrib.auth.decorators import login_required,user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q,Sum, Count
from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO
from django.conf import settings
from datetime import datetime
from .forms import ClientForm, InvoiceForm, UserLoginForm, SettingsForm, ServiceForm
from .models import Client,Invoice,Settings,Service,InvoiceService
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,logout,login as auth_login
from random import randint
from uuid import uuid4
import json


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
    invoices = Invoice.objects.all().select_related('client').prefetch_related('service')
    
    context = {'invoices': invoices}
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
def edit_client(request, client_id):
    """Edit an existing service"""
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        # Manually handle form data
        clientname = request.POST.get('clientname')
        emailAddress = request.POST.get('emailAddress')
        adress = request.POST.get('adress')
        mf = request.POST.get('mf')
        
        try:
            # Update service fields
            client.clientname = clientname
            client.emailAddress = emailAddress if emailAddress else ''
            client.adress = adress if adress else ''
            client.mf = mf if mf else ''            

            client.save()
            messages.success(request, f'Client "{client.clientname}" updated successfully!')
            
        except (ValueError, TypeError) as e:
            messages.error(request, f'Invalid data provided: {str(e)}')
    
    return redirect('clients')

@login_required
def settings_view(request):
    """View and edit company settings"""
    settings = Settings.objects.first()
    
    if request.method == 'POST':
        if settings:
            form = SettingsForm(request.POST, request.FILES, instance=settings)
        else:
            form = SettingsForm(request.POST, request.FILES)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings updated successfully!')
            return redirect('settings_view')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        if settings:
            form = SettingsForm(instance=settings)
        else:
            form = SettingsForm()
    
    context = {
        'form': form,
        'settings': settings,
    }
    
    return render(request, 'sales/settings.html', context)

@login_required
def delete_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    client.delete()
    messages.success(request, "Client removed successfully")
    return redirect('clients')

@login_required
def invoices_list(request):
    """Display all invoices with filtering and search"""
    invoices = Invoice.objects.all().select_related('client').prefetch_related('service')
    
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
    
    # Get all clients and services for dropdowns
    clients = Client.objects.all().order_by('clientname')
    services = Service.objects.all().order_by('title')
        # Get Settings for form defaults
    settings = Settings.objects.first()
    
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
        'services': services,
        'form': InvoiceForm(),
        'total_invoices': total_invoices,
        'current_invoices': current_invoices,
        'overdue_invoices': overdue_invoices,
        'paid_invoices': paid_invoices,
        'settings': settings,
    }
    
    return render(request, 'sales/invoice_service.html', context)

@login_required
def invoice_create(request):
    """Create a new invoice with inventory management"""
    if request.method != 'POST':
        return redirect('invoices_list')

    try:
        with transaction.atomic():
            # Required fields
            title = request.POST.get('title', '').strip()
            client_id = request.POST.get('client')

            if not title:
                messages.error(request, 'Invoice title is required.')
                return redirect('invoices_list')

            if not client_id:
                messages.error(request, 'Client is required.')
                return redirect('invoices_list')

            try:
                client = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                messages.error(request, 'Selected client does not exist.')
                return redirect('invoices_list')

            # Basic values
            status = request.POST.get('status', 'CURRENT')
            notes = request.POST.get('notes', '')
            # Get Settings for defaults
            settings = Settings.objects.first()
            
            # TVA and Timbre Fiscal - use form values or fall back to Settings
            tva_input = request.POST.get('tva', '').strip()
            if tva_input:
                tva = float(tva_input)
            elif settings and settings.tva:
                tva = float(settings.tva)
            else:
                tva = 19.00
            
            timbre_input = request.POST.get('timbre_fiscal', '').strip()
            if timbre_input:
                timbre_fiscal = float(timbre_input)
            elif settings and settings.dt:
                timbre_fiscal = float(settings.dt)
            else:
                timbre_fiscal = 1.000
            
            discount = float(request.POST.get('discount', 0.00))

            # Get services from arrays
            service_ids = request.POST.getlist('service_id[]')

            if not service_ids:
                messages.error(request, 'You must add at least one service.')
                return redirect('invoices_list')

            # Create invoice
            invoice = Invoice.objects.create(
                title=title,
                client=client,
                status=status,
                notes=notes,
                tva=tva,
                timbre_fiscal=timbre_fiscal,
                discount=discount
            )

            # Add services (if you have a Service model and InvoiceService model)
            for service_id in service_ids:
                if not service_id:
                    continue
                
                try:
                    service = Service.objects.get(id=service_id)
                    # Assuming you have InvoiceService model
                    InvoiceService.objects.create(
                        invoice=invoice,
                        service=service,
                        unit_price=service.price
                    )
                except Service.DoesNotExist:
                    pass  # Skip if service doesn't exist

            messages.success(request, f'Invoice "{invoice.title}" created successfully.')
            return redirect('invoice_detail', invoice.id)

    except Service.DoesNotExist:
        messages.error(request, 'One of the selected services does not exist.')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error creating invoice: {str(e)}')

    return redirect('invoices_list')


@login_required
def invoice_edit(request, invoice_id):
    """Edit an existing invoice and adjust inventory properly"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    next_page = request.POST.get('next', 'detail')

    if request.method != 'POST':
        return redirect('invoice_detail', invoice.id)

    try:
        with transaction.atomic():
            # Basic fields
            title = request.POST.get('title', '').strip()
            status = request.POST.get('status')
            notes = request.POST.get('notes', '')

            if not title:
                raise ValueError('Invoice title is required.')

            invoice.title = title
            invoice.status = status
            invoice.notes = notes

            # Numeric fields
            if request.POST.get('tva'):
                invoice.tva = float(request.POST['tva'])

            if request.POST.get('timbre_fiscal'):
                invoice.timbre_fiscal = float(request.POST['timbre_fiscal'])

            if request.POST.get('discount'):
                invoice.discount = float(request.POST['discount'])

            # Client
            client_id = request.POST.get('client')
            if client_id:
                try:
                    invoice.client = Client.objects.get(id=client_id)
                except Client.DoesNotExist:
                    raise ValueError('Selected client does not exist.')


            # Get services from arrays
            service_ids = request.POST.getlist('service_id[]')

            if not service_ids:
                raise ValueError('You must add at least one service.')
            # Delete previous invoice services and services
            invoice.invoice_services.all().delete()
            # If you have services: invoice.invoice_services.all().delete()

            # Add new services
            for service_id in service_ids:
                if not service_id:
                    continue
                
                try:
                    service = Service.objects.get(id=service_id)
                    InvoiceService.objects.create(
                        invoice=invoice,
                        service=service,
                        unit_price=service.price
                    )
                except Service.DoesNotExist:
                    pass

            invoice.save()
            messages.success(request, f'Invoice "{invoice.title}" updated successfully.')

    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error updating invoice: {str(e)}')

    if next_page == 'detail':
        return redirect('invoice_detail', invoice.id)

    return redirect('invoices_list')

@login_required
def invoice_detail(request, invoice_id):
    """View invoice details with inventory-tracked services"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # Get invoice services with their quantities
    invoice_services = invoice.invoice_services.select_related('service').all()
    
    # Calculate amounts
    subtotal = invoice.calculate_service_subtotal()
    discount_amount = invoice.calculate_discount_amount()
    subtotal_after_discount = invoice.calculate_subtotal_after_discount()
    tva_amount = invoice.calculate_tva_amount()
    total = invoice.calculate_total()
    
    # Prepare services with line totals
    services_with_totals = []
    invoice_currency = 'TND'
    

    for invoice_service in invoice_services:
        service = invoice_service.service
        if not invoice_currency or invoice_currency == 'TND':
            invoice_currency = service.currency or 'TND'
        
        services_with_totals.append({
            'service': service,
            'unit_price': invoice_service.unit_price,      # Price at time of invoice
            'line_total': invoice_service.get_line_total(),       
        })
    
    # Get all clients and services for edit modal
    clients = Client.objects.all().order_by('clientname')
    all_services = Service.objects.all().order_by('title')
    # Get settings
    try:
        p_settings = Settings.objects.first()
    except Exception as e:
        p_settings = None
    
    context = {
        'invoice': invoice,
        'invoice_services': invoice_services,
        'services_with_totals': services_with_totals,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'subtotal_after_discount': subtotal_after_discount,
        'tva_amount': tva_amount,
        'total': total,
        'invoiceCurrency': invoice_currency,
        'clients': clients,
        'all_services': all_services,
        'p_settings': p_settings,
    }
    
    return render(request, 'sales/invoice_detail_service.html', context)

@login_required
def invoice_delete(request, invoice_id):
    """Delete an invoice and restore inventory"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.method == 'POST':
        invoice_title = invoice.title
        # The delete method in the model will automatically restore inventory
        invoice.delete()
        messages.success(request, f'Invoice "{invoice_title}" deleted and inventory restored!')
    
    return redirect('invoices_list')

@login_required
def export_invoices(request):
    """Export all invoices to Excel"""
    invoices = Invoice.objects.all().select_related('client', 'service').order_by('-date_created')
    
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    
    # Define headers
    headers = ['Invoice ID', 'Unique ID', 'Title', 'Client', 'Service', 'Status', 'Date Created', 'Last Updated', 'Notes']
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
            invoice.client.clientname if invoice.client else 'No Client',
            invoice.service.title if invoice.service else 'No Service',
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
    headers = ['Title', 'Client Name', 'Service Title', 'Status', 'Notes']
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
        'Sample Service',
        'CURRENT',
        'This is a sample invoice note'
    ])
    ws.append([
        'Sample Invoice 2',
        'Another Client',
        'Another Service',
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
        ['3. Service Title - Exact service title from your system'],
        ['4. Status - Invoice status: CURRENT, PAID, or OVERDUE'],
        ['5. Notes - Additional notes or comments'],
        [''],
        ['Important Notes:'],
        ['- Do not modify the header row'],
        ['- Title and Client Name are required'],
        ['- Client Name must match exactly with existing clients'],
        ['- service Title must match exactly with existing Services'],
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
            service_title_idx = headers.index('Service Title') if 'Service Title' in headers else None
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
                        client = Client.objects.get(clientname=client_name)
                    except Client.DoesNotExist:
                        error_count += 1
                        print(f"Row {row_num}: Client '{client_name}' not found")
                        continue
                    
                    # Get service if specified
                    service = None
                    if service_title_idx is not None and row[service_title_idx]:
                        try:
                            service = Service.objects.get(title=row[service_title_idx])
                        except service.DoesNotExist:
                            print(f"Row {row_num}: Service '{row[service_title_idx]}' not found, skipping service")
                    
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
                                'service': service,
                                'status': status,
                                'notes': notes,
                            }
                        )
                        
                        if not created:
                            invoice.client = client
                            invoice.service = service
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
                            service=service,
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

def service_view(request):
    """Display all services with filtering and search"""
    services = Service.objects.all()
    
    # Search filter
    search_query = request.GET.get('search', '')
    if search_query:
        services = services.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Category filter (if you have categories)
    category = request.GET.get('category', '')
    if category:
        services = services.filter(category_id=category)
    
    # Sorting
    sort_by = request.GET.get('sort', 'title')
    services = services.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(services, 20)  # 20 services per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter dropdown (if applicable)
    # categories = Category.objects.all()
    
    context = {
        'services': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'form': ServiceForm(),
        # 'categories': categories,
    }
    
    return render(request, 'sales/services.html', context)

@login_required
def add_service(request):
    """Add a single service"""
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            # Add any additional fields if needed
            # service.created_by = request.user
            service.save()
            messages.success(request, f'Service "{service.title}" added successfully!')
            return redirect('services_list')
        else:
            messages.error(request, 'Please correct the errors below.')
            # Return to the same page with errors
            services = Service.objects.all().order_by('title')
            context = {
                'services': services,
                'form': form,
            }
            return render(request, 'sales/services.html', context)
    
    return redirect('services_list')

@login_required
def edit_service(request, service_id):
    """Edit an existing service"""
    service = get_object_or_404(Service, id=service_id)
    
    if request.method == 'POST':
        # Manually handle form data
        title = request.POST.get('title')
        currency = request.POST.get('currency')
        description = request.POST.get('description')
        price = request.POST.get('price')
        
        try:
            # Update service fields
            service.title = title
            service.currency = currency if currency else 'TND'
            service.description = description if description else ''
            service.price = float(price) if price else 0.0

            
            service.save()
            messages.success(request, f'Service "{service.title}" updated successfully!')
            
        except (ValueError, TypeError) as e:
            messages.error(request, f'Invalid data provided: {str(e)}')
    
    return redirect('services_list')

@login_required
def delete_service(request, service_id):
    """Delete a service"""
    service = get_object_or_404(Service, id=service_id)
    
    if request.method == 'POST':
        service_title = service.title
        service.delete()
        messages.success(request, f'Service "{service_title}" deleted successfully!')
    
    return redirect('services_list')
