from django.contrib.auth.decorators import login_required,user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.db.models import Q,Sum, Count
from django.db import transaction
from django.db.models import ProtectedError
from io import BytesIO
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse
from .forms import ClientForm, InvoiceForm, SupplierForm, UserLoginForm, SettingsForm, ServiceForm, ClientTransactionForm, SupplierTransactionForm, SupplyForm, PurchaseForm, ElfatooraAccountForm
from .models import Client,Invoice,Settings,Service,InvoiceService,Supplier,ClientTransaction, SupplierTransaction, Supply, Purchase, PurchaseLine, InvoiceSupplyUsage, CreditNote, BonLivraison, BonLivraisonLine, Devis
from payment.models import Retenu, PurchaseRetenu
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,logout,login as auth_login
from random import randint
from uuid import uuid4
import json
from num2words import num2words
from decimal import Decimal
from .utilities import num2words_tnd_fr
from lxml import etree
from io import BytesIO
from collections import defaultdict
from datetime import datetime

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
    return redirect('login')


@login_required
def dashboard(request):
    now = datetime.now()

    # Recent invoices (single query with joins)
    invoices = (
        Invoice.objects
        .select_related('client')
        .prefetch_related('invoice_services__service')
        .order_by('-date_created')[:10]
    )

    # Counts via single aggregated query
    invoice_stats = Invoice.objects.aggregate(
        total=Count('id'),
        outstanding_count=Count('id', filter=Q(status__in=['CURRENT', 'OVERDUE'])),
        paid_month_count=Count('id', filter=Q(
            status='PAID',
            date_created__month=now.month,
            date_created__year=now.year,
        )),
        overdue_count=Count('id', filter=Q(status='OVERDUE')),
    )

    # Outstanding amount — need Python-side calc but single prefetched query
    outstanding_invoices = list(
        Invoice.objects
        .filter(status__in=['CURRENT', 'OVERDUE'])
        .prefetch_related('invoice_services__service')
    )
    outstanding_amount = sum(inv.calculate_total() for inv in outstanding_invoices)

    # Paid this month
    paid_this_month_invoices = list(
        Invoice.objects
        .filter(status='PAID', date_created__month=now.month, date_created__year=now.year)
        .prefetch_related('invoice_services__service')
    )
    paid_this_month_amount = sum(inv.calculate_total() for inv in paid_this_month_invoices)

    # Devis stats (single query)
    devis_stats = Devis.objects.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        accepted=Count('id', filter=Q(status='ACCEPTED')),
        rejected=Count('id', filter=Q(status='REJECTED')),
    )

    # Avoir stats (single query + Python sum for TTC)
    avoirs_count = CreditNote.objects.count()
    avoirs_total_ttc = sum(
        a.calculate_total()
        for a in CreditNote.objects.only('amount_ht', 'tva')
    )

    # BL stats (single query)
    bl_stats = BonLivraison.objects.aggregate(
        total=Count('id'),
        draft=Count('id', filter=Q(status='DRAFT')),
        sent=Count('id', filter=Q(status='SENT')),
        delivered=Count('id', filter=Q(status='DELIVERED')),
    )

    # Client count + debtors
    clients_count = Client.objects.count()
    debtors = []
    for c in Client.objects.all():
        bal = c.get_balance()
        if bal > Decimal('0'):
            debtors.append({'client': c, 'balance': bal})
    debtors.sort(key=lambda d: d['balance'], reverse=True)

    context = {
        'invoices': invoices,
        'total_invoices': invoice_stats['total'],
        'outstanding_amount': outstanding_amount,
        'outstanding_count': invoice_stats['outstanding_count'],
        'paid_this_month_amount': paid_this_month_amount,
        'overdue_count': invoice_stats['overdue_count'],
        'currency': 'TND',
        # Devis
        'devis_total': devis_stats['total'],
        'devis_pending': devis_stats['pending'],
        'devis_accepted': devis_stats['accepted'],
        'devis_rejected': devis_stats['rejected'],
        # Avoirs
        'avoirs_count': avoirs_count,
        'avoirs_total_ttc': avoirs_total_ttc,
        # BL
        'bl_total': bl_stats['total'],
        'bl_draft': bl_stats['draft'],
        'bl_sent': bl_stats['sent'],
        'bl_delivered': bl_stats['delivered'],
        # Clients
        'clients_count': clients_count,
        'debtors': debtors,
    }
    return render(request, "sales/dashboard.html", context)


@login_required
def clients(request):
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'New Client Added')
            return redirect('clients')
        else:
            messages.error(request, 'Problem processing your request')
            return redirect('clients')

    clients_qs = Client.objects.all().order_by('clientname')

    search_query = request.GET.get('search', '').strip()
    if search_query:
        clients_qs = clients_qs.filter(
            Q(clientname__icontains=search_query) |
            Q(emailAddress__icontains=search_query) |
            Q(adress__icontains=search_query)
        )

    status_filter = request.GET.get('status', '')
    if status_filter:
        clients_qs = clients_qs.filter(status=status_filter)

    # Debtors: clients with positive balance (owe money)
    debtors = []
    for c in clients_qs:
        bal = c.get_balance()
        if bal > Decimal('0'):
            debtors.append({'client': c, 'balance': bal})
    debtors.sort(key=lambda d: d['balance'], reverse=True)

    form = ClientForm()
    transaction_form = ClientTransactionForm()
    return render(request, 'sales/clients.html', {
        'clients': clients_qs,
        'debtors': debtors,
        'form': form,
        'transaction_form': transaction_form,
        'search_query': search_query,
        'status_filter': status_filter,
    })

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
def delete_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    client.delete()
    messages.success(request, "Client removed successfully")
    return redirect('clients')


@login_required
def client_transactions(request, client_id):
    """AJAX endpoint: return client transactions and balance as JSON"""
    client = get_object_or_404(Client, id=client_id)
    transactions = client.transactions.select_related('invoice', 'credit_note').order_by('date_created')

    running_balance = Decimal('0')
    transaction_list = []
    for txn in transactions:
        if txn.transaction_type == 'DEBIT':
            running_balance += txn.amount
        else:
            running_balance -= txn.amount

        transaction_list.append({
            'id': txn.id,
            'date': txn.date_created.strftime('%Y-%m-%d %H:%M') if txn.date_created else '',
            'type': txn.transaction_type,
            'source': txn.get_source_display(),
            'description': txn.description or '',
            'amount': float(txn.amount),
            'running_balance': float(running_balance),
            'invoice_id': txn.invoice_id,
            'invoice_ref': txn.invoice.uniqueId if txn.invoice else None,
            'credit_note_id': txn.credit_note_id,
            'credit_note_ref': txn.credit_note.uniqueId if txn.credit_note else None,
        })

    return JsonResponse({
        'success': True,
        'client_name': client.clientname,
        'balance': float(client.get_balance()),
        'transactions': transaction_list,
    })


@login_required
def client_add_transaction(request, client_id):
    """Add a manual credit/debit entry for a client, optionally linked to an invoice."""
    client = get_object_or_404(Client, id=client_id)

    if request.method == 'POST':
        form = ClientTransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.client = client
            txn.source = 'MANUAL'

            # Link to invoice and update amount_paid for CREDIT transactions
            invoice_id = request.POST.get('invoice_id', '').strip()
            if invoice_id and txn.transaction_type == 'CREDIT':
                try:
                    invoice = Invoice.objects.prefetch_related('invoice_services').get(id=invoice_id, client=client)
                    txn.invoice = invoice
                    remaining = invoice.calculate_total() - invoice.amount_paid
                    applied = min(Decimal(str(txn.amount)), remaining)
                    if applied > 0:
                        invoice.amount_paid += applied
                        if invoice.amount_paid >= invoice.calculate_total():
                            invoice.status = 'PAID'
                        invoice.save()
                except Invoice.DoesNotExist:
                    pass

            txn.save()
            messages.success(request, f'Transaction ajoutée pour "{client.clientname}"')
        else:
            messages.error(request, 'Données de transaction invalides')

    return redirect('clients')


@login_required
def client_delete_transaction(request, transaction_id):
    """Delete a single ledger entry."""
    txn = get_object_or_404(ClientTransaction, id=transaction_id)
    if request.method == 'POST':
        txn.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@login_required
def client_unpaid_invoices(request, client_id):
    """AJAX: return list of unpaid/partially-paid invoices for a client with remaining balance."""
    client = get_object_or_404(Client, id=client_id)
    invoices = (
        Invoice.objects
        .filter(client=client)
        .exclude(status='PAID')
        .prefetch_related('invoice_services')
        .order_by('-date_created')
    )
    result = []
    for inv in invoices:
        total = inv.calculate_total()
        remaining = total - inv.amount_paid
        if remaining > 0:
            result.append({
                'id': inv.id,
                'ref': f'INV-{inv.uniqueId}' if inv.uniqueId else f'#{inv.id}',
                'title': inv.title or '',
                'total': float(total),
                'amount_paid': float(inv.amount_paid),
                'remaining': float(remaining),
            })
    return JsonResponse({'invoices': result})

@login_required
def mf_map(request):
    entity_type = request.GET.get('type', 'client')
    if entity_type == 'supplier':
        data = Supplier.get_mf_map()
    else:
        data = Client.get_mf_map()
    return JsonResponse(data)


@login_required
def suppliers(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'New Supplier Added')
            return redirect('suppliers')
        else:
            messages.error(request, 'Problem processing your request')
            return redirect('suppliers')

    suppliers_qs = Supplier.objects.all().order_by('name')

    search_query = request.GET.get('search', '').strip()
    if search_query:
        suppliers_qs = suppliers_qs.filter(
            Q(name__icontains=search_query) |
            Q(emailAddress__icontains=search_query) |
            Q(adress__icontains=search_query)
        )

    status_filter = request.GET.get('status', '')
    if status_filter:
        suppliers_qs = suppliers_qs.filter(status=status_filter)

    form = SupplierForm()
    transaction_form = SupplierTransactionForm()
    return render(request, 'sales/supplier.html', {
        'Suppliers': suppliers_qs,
        'form': form,
        'transaction_form': transaction_form,
        'search_query': search_query,
        'status_filter': status_filter,
    })

@login_required
def edit_supplier(request, client_id):
    """Edit an existing service"""
    supplier = get_object_or_404(Supplier, id=client_id)
    
    if request.method == 'POST':
        # Manually handle form data
        name = request.POST.get('name')
        emailAddress = request.POST.get('emailAddress')
        adress = request.POST.get('adress')
        mf = request.POST.get('mf')
        
        try:
            # Update service fields
            supplier.name = name
            supplier.emailAddress = emailAddress if emailAddress else ''
            supplier.adress = adress if adress else ''
            supplier.mf = mf if mf else ''            

            supplier.save()
            messages.success(request, f'Supplier "{supplier.name}" updated successfully!')
            
        except (ValueError, TypeError) as e:
            messages.error(request, f'Invalid data provided: {str(e)}')
    
    return redirect('suppliers')

@login_required
def delete_supplier(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.delete()
    messages.success(request, "Supplier removed successfully")
    return redirect('suppliers')


@login_required
def supplier_transactions(request, supplier_id):
    """AJAX endpoint: return supplier transactions and balance as JSON"""
    supplier = get_object_or_404(Supplier, id=supplier_id)
    transactions = supplier.supplier_transactions.all().order_by('date_created')

    running_balance = Decimal('0')
    transaction_list = []
    for txn in transactions:
        if txn.transaction_type == 'CREDIT':
            running_balance += txn.amount
        else:
            running_balance -= txn.amount

        transaction_list.append({
            'id': txn.id,
            'date': txn.date_created.strftime('%Y-%m-%d %H:%M') if txn.date_created else '',
            'type': txn.transaction_type,
            'source': txn.get_source_display(),
            'description': txn.description or '',
            'amount': float(txn.amount),
            'running_balance': float(running_balance),
            'purchase_id': txn.purchase_id,
            'purchase_ref': txn.purchase.uniqueId if txn.purchase else None,
        })

    return JsonResponse({
        'success': True,
        'supplier_name': supplier.name,
        'balance': float(supplier.get_balance()),
        'transactions': transaction_list,
    })


@login_required
def supplier_add_transaction(request, supplier_id):
    """Add a manual credit/debit entry for a supplier"""
    supplier = get_object_or_404(Supplier, id=supplier_id)

    if request.method == 'POST':
        form = SupplierTransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.supplier = supplier
            txn.source = 'MANUAL'
            txn.save()
            messages.success(request, f'Transaction ajoutée pour "{supplier.name}"')
        else:
            messages.error(request, 'Données de transaction invalides')

    return redirect('suppliers')


# ============ SUPPLIES CRUD ============

@login_required
def supplies_list(request):
    """Display all supplies"""
    supplies = Supply.objects.all().select_related('preferred_supplier')

    search_query = request.GET.get('search', '').strip()
    if search_query:
        supplies = supplies.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    category_filter = request.GET.get('category', '')
    if category_filter:
        supplies = supplies.filter(category=category_filter)

    low_stock_filter = request.GET.get('low_stock', '')
    if low_stock_filter:
        # is_low_stock is a property; filter via DB expression instead
        from django.db.models import F
        supplies = supplies.filter(stock_quantity__lte=F('min_stock'))

    form = SupplyForm()
    suppliers_qs = Supplier.objects.all().order_by('name')
    return render(request, 'sales/supplies.html', {
        'supplies': supplies,
        'form': form,
        'suppliers': suppliers_qs,
        'search_query': search_query,
        'category_filter': category_filter,
        'low_stock_filter': low_stock_filter,
        'category_choices': Supply.CATEGORY_CHOICES,
    })


@login_required
def supply_create(request):
    """Create a new supply"""
    if request.method == 'POST':
        form = SupplyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fourniture ajoutée avec succès')
        else:
            messages.error(request, 'Erreur lors de l\'ajout de la fourniture')
    return redirect('supplies_list')


@login_required
def supply_edit(request, supply_id):
    """Edit an existing supply"""
    supply = get_object_or_404(Supply, id=supply_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        unit = request.POST.get('unit')
        unit_price = request.POST.get('unit_price')
        stock_quantity = request.POST.get('stock_quantity')
        min_stock = request.POST.get('min_stock')
        preferred_supplier_id = request.POST.get('preferred_supplier')
        description = request.POST.get('description')

        try:
            supply.name = name
            supply.category = category if category else 'raw_material'
            supply.unit = unit if unit else 'pièce'
            supply.unit_price = Decimal(unit_price) if unit_price else Decimal('0')
            supply.stock_quantity = Decimal(stock_quantity) if stock_quantity else Decimal('0')
            supply.min_stock = Decimal(min_stock) if min_stock else Decimal('0')
            supply.description = description if description else ''
            supply.apply_fodec = request.POST.get('apply_fodec') == 'on'

            if preferred_supplier_id:
                supply.preferred_supplier = Supplier.objects.get(id=preferred_supplier_id)
            else:
                supply.preferred_supplier = None

            supply.save()
            messages.success(request, f'Fourniture "{supply.name}" modifiée avec succès')
        except (ValueError, TypeError) as e:
            messages.error(request, f'Données invalides : {str(e)}')

    return redirect('supplies_list')


@login_required
def supply_delete(request, supply_id):
    """Delete a supply"""
    supply = get_object_or_404(Supply, id=supply_id)
    if request.method == 'POST':
        supply_name = supply.name
        try:
            supply.delete()
            messages.success(request, f'Fourniture "{supply_name}" supprimée avec succès')
        except ProtectedError:
            messages.error(
                request,
                f'Impossible de supprimer "{supply_name}" car elle est utilisée dans des commandes d\'achat. '
                'Supprimez d\'abord les lignes d\'achat associées.'
            )
    return redirect('supplies_list')


# ============ PURCHASES CRUD ============

@login_required
def purchases_list(request):
    """Display all purchases"""
    purchases = Purchase.objects.all().select_related('supplier').prefetch_related(
        'purchase_lines',     # needed for calculate_total — supply details not required
        'purchase_retenues',  # needed for the XML download button check — retenu_type details not required
    )

    search_query = request.GET.get('search', '')
    if search_query:
        purchases = purchases.filter(
            Q(uniqueId__icontains=search_query) |
            Q(supplier__name__icontains=search_query) |
            Q(notes__icontains=search_query)
        )

    status_filter = request.GET.get('status', '')
    if status_filter:
        purchases = purchases.filter(status=status_filter)

    context = {
        'purchases': purchases,
        'suppliers': Supplier.objects.all().order_by('name'),
        'supplies': Supply.objects.all().order_by('name'),
        'form': PurchaseForm(),
        # retenu_types omitted — only used in the AJAX purchase detail partial
    }
    return render(request, 'sales/purchases.html', context)


@login_required
def purchase_create(request):
    """Create a new purchase with line items"""
    if request.method != 'POST':
        return redirect('purchases_list')

    try:
        with transaction.atomic():
            supplier_id = request.POST.get('supplier')
            if not supplier_id:
                messages.error(request, 'Le fournisseur est requis.')
                return redirect('purchases_list')

            try:
                supplier = Supplier.objects.get(id=supplier_id)
            except Supplier.DoesNotExist:
                messages.error(request, 'Fournisseur introuvable.')
                return redirect('purchases_list')

            notes = request.POST.get('notes', '')
            tva = request.POST.get('tva', '19.00').strip()
            discount = request.POST.get('discount', '0.00').strip()
            timbre = request.POST.get('timbre_fiscal', '1.000').strip()

            purchase = Purchase.objects.create(
                supplier=supplier,
                notes=notes,
                tva=Decimal(tva) if tva else Decimal('19.00'),
                discount=Decimal(discount) if discount else Decimal('0.00'),
                timbre_fiscal=Decimal(timbre) if timbre else Decimal('1.000'),
            )

            supply_ids = request.POST.getlist('supply_id[]')
            quantities = request.POST.getlist('quantity[]')
            unit_prices = request.POST.getlist('line_unit_price[]')

            if not supply_ids:
                messages.error(request, 'Vous devez ajouter au moins une ligne.')
                purchase.delete()
                return redirect('purchases_list')

            for i, supply_id in enumerate(supply_ids):
                if not supply_id:
                    continue
                try:
                    supply = Supply.objects.get(id=supply_id)
                    qty = Decimal(quantities[i]) if i < len(quantities) and quantities[i] else Decimal('1')
                    price = Decimal(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else supply.unit_price
                    PurchaseLine.objects.create(
                        purchase=purchase,
                        supply=supply,
                        quantity=qty,
                        unit_price=price,
                        has_fodec=supply.apply_fodec,
                    )
                except Supply.DoesNotExist:
                    pass

            messages.success(request, f'Achat #{purchase.uniqueId} créé avec succès.')
            return redirect('purchases_list')

    except Exception as e:
        messages.error(request, f'Erreur lors de la création de l\'achat : {str(e)}')

    return redirect('purchases_list')


@login_required
def purchase_detail(request, purchase_id):
    """View purchase details"""
    purchase = get_object_or_404(Purchase, id=purchase_id)
    purchase_lines = purchase.purchase_lines.select_related('supply').all()

    subtotal = purchase.calculate_subtotal()
    discount_amount = purchase.calculate_discount_amount()
    subtotal_after_discount = purchase.calculate_subtotal_after_discount()
    total_fodec = purchase.calculate_total_fodec()
    tva_amount = purchase.calculate_tva_amount()
    total_before_timbre = purchase.calculate_total_before_timbre()
    total = purchase.calculate_total()
    total_retenue = purchase.get_total_retenue()
    net_amount = purchase.get_net_amount()

    retenu_types = Retenu.objects.filter(is_active=True).order_by('category', 'rate')
    purchase_retenues = purchase.purchase_retenues.select_related('retenu_type').all()

    suppliers_qs = Supplier.objects.all().order_by('name')
    supplies = Supply.objects.all().order_by('name')

    context = {
        'purchase': purchase,
        'purchase_lines': purchase_lines,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'subtotal_after_discount': subtotal_after_discount,
        'total_fodec': total_fodec,
        'tva_amount': tva_amount,
        'total_before_timbre': total_before_timbre,
        'total': total,
        'total_retenue': total_retenue,
        'net_amount': net_amount,
        'retenu_types': retenu_types,
        'purchase_retenues': purchase_retenues,
        'suppliers': suppliers_qs,
        'supplies': supplies,
    }
    return render(request, 'sales/purchase_detail.html', context)


@login_required
def purchase_edit(request, purchase_id):
    """Edit an existing purchase"""
    purchase = get_object_or_404(Purchase, id=purchase_id)

    if request.method != 'POST':
        return redirect('purchases_list')

    try:
        with transaction.atomic():
            supplier_id = request.POST.get('supplier')
            if supplier_id:
                try:
                    purchase.supplier = Supplier.objects.get(id=supplier_id)
                except Supplier.DoesNotExist:
                    raise ValueError('Fournisseur introuvable.')

            purchase.notes = request.POST.get('notes', '')
            if request.POST.get('tva'):
                purchase.tva = Decimal(request.POST['tva'])
            if request.POST.get('discount'):
                purchase.discount = Decimal(request.POST['discount'])
            if request.POST.get('timbre_fiscal'):
                purchase.timbre_fiscal = Decimal(request.POST['timbre_fiscal'])

            # Rebuild lines
            purchase.purchase_lines.all().delete()

            supply_ids = request.POST.getlist('supply_id[]')
            quantities = request.POST.getlist('quantity[]')
            unit_prices = request.POST.getlist('line_unit_price[]')

            if not supply_ids:
                raise ValueError('Vous devez ajouter au moins une ligne.')

            for i, supply_id in enumerate(supply_ids):
                if not supply_id:
                    continue
                try:
                    supply = Supply.objects.get(id=supply_id)
                    qty = Decimal(quantities[i]) if i < len(quantities) and quantities[i] else Decimal('1')
                    price = Decimal(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else supply.unit_price
                    PurchaseLine.objects.create(
                        purchase=purchase,
                        supply=supply,
                        quantity=qty,
                        unit_price=price,
                        has_fodec=supply.apply_fodec,
                    )
                except Supply.DoesNotExist:
                    pass

            purchase.save()
            messages.success(request, f'Achat #{purchase.uniqueId} modifié avec succès.')

    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Erreur : {str(e)}')

    return redirect('purchases_list')


@login_required
def purchase_delete(request, purchase_id):
    """Delete a purchase and reverse stock/ledger if confirmed"""
    purchase = get_object_or_404(Purchase, id=purchase_id)

    if request.method == 'POST':
        purchase_ref = purchase.uniqueId

        # If purchase was received, reverse stock
        if purchase.status in ('RECEIVED', 'PAID'):
            for line in purchase.purchase_lines.all():
                line.supply.stock_quantity -= line.quantity
                line.supply.save()

            # Only reverse the ledger CREDIT if not yet paid.
            # For PAID purchases the confirm CREDIT and payment DEBIT already cancel out (balance = 0).
            if purchase.status == 'RECEIVED' and purchase.supplier:
                purchase_total = purchase.calculate_total()
                SupplierTransaction.objects.create(
                    supplier=purchase.supplier,
                    purchase=None,
                    transaction_type='DEBIT',
                    source='PURCHASE_DELETED',
                    amount=purchase_total,
                    description=f'Annulation achat #{purchase_ref}'
                )

        purchase.delete()
        messages.success(request, f'Achat #{purchase_ref} supprimé avec succès.')

    return redirect('purchases_list')


@login_required
def purchase_confirm(request, purchase_id):
    """Confirm/receive a purchase: increment stock and create supplier CREDIT"""
    purchase = get_object_or_404(Purchase, id=purchase_id)

    if request.method == 'POST':
        if purchase.status not in ('DRAFT', 'CONFIRMED'):
            messages.warning(request, 'Cet achat a déjà été reçu.')
            return redirect('purchases_list')

        with transaction.atomic():
            # Increment stock for each line
            for line in purchase.purchase_lines.all():
                line.supply.stock_quantity += line.quantity
                line.supply.save()

            # Create supplier CREDIT transaction (we owe them)
            purchase_total = purchase.calculate_total()
            SupplierTransaction.objects.create(
                supplier=purchase.supplier,
                purchase=purchase,
                transaction_type='CREDIT',
                source='PURCHASE_CONFIRMED',
                amount=purchase_total,
                description=f'Achat #{purchase.uniqueId} reçu'
            )

            purchase.status = 'RECEIVED'
            purchase.save()

        messages.success(request, f'Achat #{purchase.uniqueId} confirmé et stock mis à jour.')

    return redirect('purchases_list')


@login_required
def process_purchase_payment(request, purchase_id):
    """Process payment for a purchase: create supplier DEBIT"""
    purchase = get_object_or_404(Purchase, id=purchase_id)

    if request.method == 'POST':
        if purchase.status == 'PAID':
            messages.warning(request, 'Cet achat est déjà payé.')
            return redirect('purchases_list')

        with transaction.atomic():
            purchase_total = purchase.calculate_total()
            SupplierTransaction.objects.create(
                supplier=purchase.supplier,
                purchase=purchase,
                transaction_type='DEBIT',
                source='PURCHASE_PAID',
                amount=purchase_total,
                description=f'Paiement achat #{purchase.uniqueId}'
            )

            purchase.status = 'PAID'
            purchase.save()

        messages.success(request, f'Paiement de l\'achat #{purchase.uniqueId} enregistré.')

    return redirect('purchases_list')


@login_required
def purchase_retenu_create(request, purchase_id):
    """Add retenu to a purchase"""
    purchase = get_object_or_404(Purchase, id=purchase_id)

    if request.method == 'POST':
        retenu_type_id = request.POST.get('retenu_type')
        base_amount = request.POST.get('base_amount')

        if retenu_type_id and base_amount:
            try:
                retenu_type = Retenu.objects.get(id=retenu_type_id)
                base = Decimal(base_amount)
                calculated = (base * retenu_type.rate) / Decimal('100')

                PurchaseRetenu.objects.create(
                    purchase=purchase,
                    retenu_type=retenu_type,
                    base_amount=base,
                    retenu_rate=retenu_type.rate,
                    retenu_amount=calculated,
                )
                messages.success(request, 'Retenue ajoutée avec succès.')
            except (Retenu.DoesNotExist, ValueError) as e:
                messages.error(request, f'Erreur : {str(e)}')
        else:
            messages.error(request, 'Données manquantes.')

    return redirect('purchases_list')


@login_required
def purchase_retenu_delete(request, retenu_id):
    """Delete a retenu from a purchase"""
    retenu = get_object_or_404(PurchaseRetenu, id=retenu_id)
    purchase_id = retenu.purchase_id

    if request.method == 'POST':
        retenu.delete()
        messages.success(request, 'Retenue supprimée.')

    return redirect('purchases_list')


# Subcategory to RS operation type mapping for XML generation
SUBCATEGORY_TO_OP_TYPE = {
    'ACQ_PM_IS': 'RS1_000001',
    'ACQ_COMMISSION_PM': 'RS1_000002',
    'ACQ_1000_2_3': 'RS1_000003',
    'ACQ_1000_OTHER': 'RS1_000004',
    'ACQ_1000_15': 'RS1_000005',
    'ACQ_COMMISSION_PP': 'RS1_000006',
    'LOYER_HOTEL': 'RS2_000001',
    'LOYER_RESIDENT': 'RS2_000002',
    'BNC_REEL': 'RS3_000001',
    'REMUN_PERFORMANCE': 'RS3_000002',
    'REMUN_ARTISTES': 'RS3_000003',
    'BNC_FORFAIT': 'RS3_000004',
    'CESSION_FONDS': 'RS4_000001',
    'CESSION_IMMEUBLE': 'RS4_000002',
    'DIVIDENDE_PP': 'RS5_000001',
    'CAPITAUX_MOB': 'RS6_000001',
    'JEUX_PARI': 'RS7_000001',
    'JETONS_PRESENCE': 'RS8_000001',
}


@login_required
def purchase_download_xml(request, purchase_id):
    """Generate RS declaration XML for a purchase's retenues using lxml directly"""


    def fmt(value):
        return str(Decimal(str(value)).quantize(Decimal('0.000')))

    purchase = get_object_or_404(Purchase, id=purchase_id)
    retenues = purchase.purchase_retenues.select_related('retenu_type').all()

    if not retenues.exists():
        messages.error(request, 'Aucune retenue à exporter.')
        return redirect('purchases_list')

    settings_obj = Settings.get_cached()
    if not settings_obj or not settings_obj.mf:
        messages.error(request, "Veuillez configurer les paramètres de l'entreprise (MF requis).")
        return redirect('purchases_list')

    supplier = purchase.supplier
    if not supplier or not supplier.mf:
        messages.error(request, 'Le fournisseur doit avoir un matricule fiscal.')
        return redirect('purchases_list')

    root = etree.Element("DeclarationsRS", VersionSchema="1.0")

    # Declarant
    declarant = etree.SubElement(root, "Declarant")
    etree.SubElement(declarant, "TypeIdentifiant").text = "1"
    etree.SubElement(declarant, "Identifiant").text = settings_obj.mf
    etree.SubElement(declarant, "CategorieContribuable").text = settings_obj.status or "PM"

    # Reference
    ref = etree.SubElement(root, "ReferenceDeclaration")
    etree.SubElement(ref, "ActeDepot").text = "0"
    etree.SubElement(ref, "AnneeDepot").text = str(purchase.date_created.year)
    etree.SubElement(ref, "MoisDepot").text = f"{purchase.date_created.month:02d}"

    ajouter = etree.SubElement(root, "AjouterCertificats")
    cert = etree.SubElement(ajouter, "Certificat")

    # Beneficiaire (supplier)
    ben = etree.SubElement(cert, "Beneficiaire")
    id_tax = etree.SubElement(ben, "IdTaxpayer")
    mf_el = etree.SubElement(id_tax, "MatriculeFiscal")
    etree.SubElement(mf_el, "TypeIdentifiant").text = "1"
    etree.SubElement(mf_el, "Identifiant").text = supplier.mf[:8]
    etree.SubElement(mf_el, "CategorieContribuable").text = supplier.status or "PM"
    etree.SubElement(ben, "Resident").text = "1"
    etree.SubElement(ben, "NometprenonOuRaisonsociale").text = supplier.name or ""
    etree.SubElement(ben, "Adresse").text = supplier.adress or ""
    etree.SubElement(ben, "Activite").text = "Fournisseur"
    infos = etree.SubElement(ben, "InfosContact")
    etree.SubElement(infos, "AdresseMail").text = supplier.emailAddress or ""
    etree.SubElement(infos, "NumTel").text = ""

    etree.SubElement(cert, "DatePayement").text = purchase.date_created.strftime('%d/%m/%Y')
    etree.SubElement(cert, "Ref_certif_chez_declarant").text = str(purchase.uniqueId)

    # Operations (one per retenu)
    ops = etree.SubElement(cert, "ListeOperations")
    totals = defaultdict(lambda: Decimal('0'))
    montant_ttc = purchase.calculate_total()
    montant_tva = purchase.calculate_tva_amount()

    for ret in retenues:
        op_type = SUBCATEGORY_TO_OP_TYPE.get(ret.retenu_type.subcategory, 'RS1_000001')
        net_servi = montant_ttc - ret.retenu_amount

        op = etree.SubElement(ops, "Operation", IdTypeOperation=op_type)
        etree.SubElement(op, "AnneeFacturation").text = str(purchase.date_created.year)
        etree.SubElement(op, "CNPC").text = "0"
        etree.SubElement(op, "P_Charge").text = "0"
        etree.SubElement(op, "MontantHT").text = fmt(ret.base_amount)
        etree.SubElement(op, "TauxRS").text = str(ret.retenu_rate)
        etree.SubElement(op, "TauxTVA").text = str(purchase.tva)
        etree.SubElement(op, "MontantTVA").text = fmt(montant_tva)
        etree.SubElement(op, "MontantTTC").text = fmt(montant_ttc)
        etree.SubElement(op, "MontantRS").text = fmt(ret.retenu_amount)
        etree.SubElement(op, "MontantNetServi").text = fmt(net_servi)

        totals["ht"] += ret.base_amount
        totals["tva"] += montant_tva
        totals["ttc"] += montant_ttc
        totals["rs"] += ret.retenu_amount
        totals["net"] += net_servi

    # Totals
    total_el = etree.SubElement(cert, "TotalPayement")
    etree.SubElement(total_el, "TotalMontantHT").text = fmt(totals["ht"])
    etree.SubElement(total_el, "TotalMontantTVA").text = fmt(totals["tva"])
    etree.SubElement(total_el, "TotalMontantTTC").text = fmt(totals["ttc"])
    etree.SubElement(total_el, "TotalMontantRS").text = fmt(totals["rs"])
    etree.SubElement(total_el, "TotalMontantNetServi").text = fmt(totals["net"])

    buffer = BytesIO()
    etree.ElementTree(root).write(buffer, encoding="UTF-8", xml_declaration=True, standalone=True, pretty_print=True)
    buffer.seek(0)

    mois = purchase.date_created.month
    trimestre = (mois - 1) // 3 + 1
    filename = f'{supplier.mf[:8]}-{purchase.date_created.year}-{trimestre}-0.xml'
    response = HttpResponse(buffer.read(), content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def invoices_list(request):
    """Display all invoices with filtering and search"""
    invoices = Invoice.objects.all().select_related('client').prefetch_related('invoice_services__service', 'credit_notes', 'retenues')

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
    
    # Calculate statistics + total in one query, before paginating
    status_counts = invoices.aggregate(
        total=Count('id'),
        current=Count('id', filter=Q(status='CURRENT')),
        overdue=Count('id', filter=Q(status='OVERDUE')),
        paid=Count('id', filter=Q(status='PAID')),
    )
    total_invoices = status_counts['total']
    current_invoices = status_counts['current']
    overdue_invoices = status_counts['overdue']
    paid_invoices = status_counts['paid']

    # Paginate — pre-populate cached_property so Paginator skips its own COUNT query
    paginator = Paginator(invoices, 20)
    paginator.__dict__['count'] = total_invoices
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get all clients and services for dropdowns
    clients = Client.objects.all().order_by('clientname')
    services = Service.objects.all().order_by('title')

    # Get Settings for form defaults (create if doesn't exist)
    settings = Settings.get_cached()
    if not settings:
        settings = Settings.objects.create(
            clientname="My Company",
            tva=Decimal('19.00'),
            dt=Decimal('1.000')
        )
    # retenu_types omitted — not referenced in invoice_service.html

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
        'current_year': timezone.now().year,
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
            client_id = request.POST.get('client')
            title = ''  # Title is now optional/empty

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
            settings = Settings.get_cached()
            
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

            # Parse optional custom date
            from datetime import datetime, time
            from django.utils import timezone as dj_tz
            custom_date_raw = request.POST.get('invoice_date', '').strip()
            custom_datetime = None
            if custom_date_raw:
                try:
                    parsed = datetime.strptime(custom_date_raw, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError('Date invalide')
                tz = dj_tz.get_current_timezone()
                custom_datetime = dj_tz.make_aware(datetime.combine(parsed, time.min), tz)

            # Parse optional custom number
            custom_number_raw = request.POST.get('invoice_number', '').strip()
            manual_number = None
            if custom_number_raw:
                try:
                    manual_number = int(custom_number_raw)
                except ValueError:
                    raise ValueError('Numéro invalide (1–999)')

            # Determine year from picked date, else today
            year = (custom_datetime.year if custom_datetime
                    else dj_tz.localtime(dj_tz.now()).year)
            unique_id = Invoice.generate_unique_id(year, manual_number=manual_number)

            # Create invoice
            invoice_kwargs = dict(
                title=title,
                client=client,
                status=status,
                notes=notes,
                tva=tva,
                timbre_fiscal=timbre_fiscal,
                discount=discount,
                uniqueId=unique_id,
            )
            if custom_datetime is not None:
                invoice_kwargs['date_created'] = custom_datetime
            invoice = Invoice.objects.create(**invoice_kwargs)

            # Add services (if you have a Service model and InvoiceService model)
            fodec_flags = request.POST.getlist('has_fodec[]')
            unit_prices = request.POST.getlist('unit_price[]')
            for i, service_id in enumerate(service_ids):
                if not service_id:
                    continue

                try:
                    service = Service.objects.get(id=service_id)
                    has_fodec = fodec_flags[i] == '1' if i < len(fodec_flags) else False
                    # Use submitted price if provided, otherwise fall back to service price
                    if i < len(unit_prices) and unit_prices[i]:
                        price = Decimal(str(unit_prices[i]))
                    else:
                        price = service.price
                    InvoiceService.objects.create(
                        invoice=invoice,
                        service=service,
                        unit_price=price,
                        has_fodec=has_fodec
                    )
                except Service.DoesNotExist:
                    pass  # Skip if service doesn't exist

            # Auto-DEBIT ledger entry
            invoice_total = invoice.calculate_total()
            ClientTransaction.objects.create(
                client=client,
                invoice=invoice,
                transaction_type='DEBIT',
                source='INVOICE_CREATED',
                amount=invoice_total,
                description=f'Facture {invoice.uniqueId} - {invoice.title}'
            )

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
            title = ''  # Title is now optional/empty
            status = request.POST.get('status')
            notes = request.POST.get('notes', '')

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

            # Custom date / number — only when not locked and not paid
            if not invoice.is_locked and (status or invoice.status) != 'PAID':
                from datetime import datetime, time
                from django.utils import timezone as dj_tz

                custom_date_raw = request.POST.get('invoice_date', '').strip()
                if custom_date_raw:
                    try:
                        parsed = datetime.strptime(custom_date_raw, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError('Date invalide')
                    tz = dj_tz.get_current_timezone()
                    invoice.date_created = dj_tz.make_aware(
                        datetime.combine(parsed, time.min), tz
                    )

                custom_number_raw = request.POST.get('invoice_number', '').strip()
                if custom_number_raw:
                    try:
                        manual_number = int(custom_number_raw)
                    except ValueError:
                        raise ValueError('Numéro invalide (1–999)')
                    year = invoice.date_created.year if invoice.date_created else dj_tz.now().year
                    invoice.uniqueId = Invoice.generate_unique_id(
                        year, manual_number=manual_number, exclude_pk=invoice.pk,
                    )

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
            fodec_flags = request.POST.getlist('has_fodec[]')
            unit_prices = request.POST.getlist('unit_price[]')
            for i, service_id in enumerate(service_ids):
                if not service_id:
                    continue

                try:
                    service = Service.objects.get(id=service_id)
                    has_fodec = fodec_flags[i] == '1' if i < len(fodec_flags) else False
                    if i < len(unit_prices) and unit_prices[i]:
                        price = Decimal(str(unit_prices[i]))
                    else:
                        price = service.price
                    InvoiceService.objects.create(
                        invoice=invoice,
                        service=service,
                        unit_price=price,
                        has_fodec=has_fodec
                    )
                except Service.DoesNotExist:
                    pass

            invoice.save()

            # Update ledger: adjust DEBIT amount to new total
            new_total = invoice.calculate_total()
            if invoice.client:
                debit_entry = ClientTransaction.objects.filter(
                    invoice=invoice,
                    source='INVOICE_CREATED',
                    transaction_type='DEBIT'
                ).first()

                if debit_entry:
                    debit_entry.amount = new_total
                    debit_entry.description = f'Facture {invoice.uniqueId} - {invoice.title}'
                    debit_entry.save()
                else:
                    # Invoice existed before ledger system
                    ClientTransaction.objects.create(
                        client=invoice.client,
                        invoice=invoice,
                        transaction_type='DEBIT',
                        source='INVOICE_CREATED',
                        amount=new_total,
                        description=f'Facture {invoice.uniqueId} - {invoice.title}'
                    )

                # Auto-CREDIT when status changes to PAID
                if status == 'PAID':
                    existing_credit = ClientTransaction.objects.filter(
                        invoice=invoice,
                        source='INVOICE_PAID',
                        transaction_type='CREDIT'
                    ).exists()
                    if not existing_credit:
                        ClientTransaction.objects.create(
                            client=invoice.client,
                            invoice=invoice,
                            transaction_type='CREDIT',
                            source='INVOICE_PAID',
                            amount=new_total,
                            description=f'Paiement facture {invoice.uniqueId} - {invoice.title}'
                        )

            messages.success(request, f'Invoice "{invoice.title}" updated successfully.')

    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error updating invoice: {str(e)}')

    if next_page == 'detail':
        return redirect('invoice_detail', invoice.id)

    return redirect('invoices_list')

@login_required
def invoice_detail(request, invoice_id=None, slug=None):
    """View invoice details with inventory-tracked services"""
    from gov.models import GovInvoice
    qs = Invoice.objects.prefetch_related(
        'invoice_services__service',
        'credit_notes',
        'retenues',
    ).select_related('client')
    if slug:
        invoice = get_object_or_404(qs, slug=slug)
    else:
        invoice = get_object_or_404(qs, id=invoice_id)

    # Uses the prefetch cache — no extra query
    invoice_services = invoice.invoice_services.all()
    
    # Calculate amounts
    subtotal = invoice.calculate_service_subtotal()
    discount_amount = invoice.calculate_discount_amount()
    subtotal_after_discount = invoice.calculate_subtotal_after_discount()
    total_fodec = invoice.calculate_total_fodec()
    tva_amount = invoice.calculate_tva_amount()
    total = invoice.calculate_total()
    total_in_words = num2words_tnd_fr(Decimal(total))
    # Prepare services with line totals
    services_with_totals = []
    invoice_currency = 'TND'
    

    for invoice_service in invoice_services:
        service = invoice_service.service
        if not invoice_currency or invoice_currency == 'TND':
            invoice_currency = service.currency or 'TND'

        services_with_totals.append({
            'service': service,
            'unit_price': invoice_service.unit_price,
            'line_total': invoice_service.get_line_ht(),
            'has_fodec': invoice_service.has_fodec,
            'fodec_amount': invoice_service.get_fodec_amount(),
        })

    
    # Get all clients and services for edit modal
    clients = Client.objects.all().order_by('clientname')
    all_services = Service.objects.all().order_by('title')
    # Get settings
    try:
        p_settings = Settings.get_cached()
    except Exception as e:
        p_settings = None
    
    context = {
        'invoice': invoice,
        'invoice_services': invoice_services,
        'services_with_totals': services_with_totals,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'subtotal_after_discount': subtotal_after_discount,
        'total_fodec': total_fodec,
        'tva_amount': tva_amount,
        'total': total,
        'total_in_words': total_in_words,
        'invoiceCurrency': invoice_currency,
        'clients': clients,
        'all_services': all_services,
        'p_settings': p_settings,
        'gov_invoice': GovInvoice.objects.filter(invoice=invoice).first() if True else None,
    }
    
    return render(request, 'sales/invoice_detail_service.html', context)


@login_required
def purchase_detail_modal(request, purchase_id):
    """Return rendered HTML for the shared purchase detail modal body."""
    purchase = get_object_or_404(
        Purchase.objects.select_related('supplier')
                        .prefetch_related('purchase_lines__supply', 'purchase_retenues__retenu_type'),
        id=purchase_id,
    )
    context = {
        'purchase': purchase,
        'suppliers': Supplier.objects.all().order_by('name'),
        'supplies': Supply.objects.all().order_by('name'),
        'retenu_types': Retenu.objects.filter(is_active=True).order_by('category', 'rate'),
    }
    return render(request, 'partials/purchase_detail_modal.html', context)


@login_required
def invoice_modal_data(request, invoice_id):
    """Return JSON data needed to populate the shared edit invoice modal."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    services = [
        {
            'service_id': inv_svc.service_id,
            'unit_price': str(inv_svc.unit_price),
            'has_fodec': inv_svc.has_fodec,
        }
        for inv_svc in invoice.invoice_services.all()
    ]
    return JsonResponse({
        'id': invoice.id,
        'status': invoice.status,
        'client_id': invoice.client_id,
        'tva': str(invoice.tva) if invoice.tva is not None else '19.00',
        'timbre_fiscal': str(invoice.timbre_fiscal) if invoice.timbre_fiscal is not None else '1.000',
        'discount': str(invoice.discount) if invoice.discount is not None else '0.00',
        'notes': invoice.notes or '',
        'services': services,
    })


@login_required
def invoice_delete(request, invoice_id):
    """Delete an invoice and restore inventory"""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.method == 'POST':
        invoice_title = invoice.title

        with transaction.atomic():
            # Delete all ledger entries tied to this invoice instead of
            # creating reversal entries that inflate the grand livre.
            ClientTransaction.objects.filter(invoice=invoice).delete()

            invoice.delete()

        messages.success(request, f'Invoice "{invoice_title}" deleted and inventory restored!')

    return redirect('invoices_list')

@login_required
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
            service.apply_fodec = request.POST.get('apply_fodec') == 'on'

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


@login_required
def settings_view(request):
    """View and edit company settings"""
    import base64 as _b64
    settings = Settings.get_cached()

    if request.method == 'POST':
        form = SettingsForm(request.POST, request.FILES, instance=settings)

        if form.is_valid():
            obj = form.save(commit=False)

            logo_file = request.FILES.get('logo_upload')
            if logo_file:
                if logo_file.size > 2 * 1024 * 1024:
                    messages.error(request, 'Le logo ne doit pas dépasser 2 Mo.')
                    return render(request, 'sales/settings.html', {'form': form, 'settings': settings})
                raw = logo_file.read()
                encoded = _b64.b64encode(raw).decode('utf-8')
                obj.clientLogo = f'data:{logo_file.content_type};base64,{encoded}'
            elif request.POST.get('clear_logo'):
                obj.clientLogo = None
            elif settings:
                obj.clientLogo = settings.clientLogo  # keep existing

            obj.save()
            messages.success(request, 'Paramètres mis à jour.')
            return redirect('settings_view')
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        form = SettingsForm(instance=settings)

    return render(request, 'sales/settings.html', {'form': form, 'settings': settings})


@login_required
def elfatoora_settings(request):
    """Manage per-tenant elfatoora credentials. Account lives in public schema."""
    from django.db import connection
    from tenants.models import Tenant, ElfatooraClientAccount

    current_schema = connection.schema_name
    connection.set_schema_to_public()
    try:
        tenant = Tenant.objects.get(schema_name=current_schema)
        account = ElfatooraClientAccount.objects.filter(tenant=tenant).first()
    finally:
        connection.set_schema(current_schema)

    if request.method == 'POST':
        form = ElfatooraAccountForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            connection.set_schema_to_public()
            try:
                if account:
                    account.username = data['username']
                    account.mf = data['mf']
                    if data['password']:
                        account.password = data['password']
                    if account.status == 'ERROR':
                        account.status = 'PENDING'
                    account.save()
                else:
                    if not data['password']:
                        form.add_error('password', 'Mot de passe requis pour créer le compte.')
                        connection.set_schema(current_schema)
                        return render(request, 'sales/elfatoora_settings.html',
                                      {'form': form, 'account': None})
                    account = ElfatooraClientAccount.objects.create(
                        tenant=tenant,
                        username=data['username'],
                        password=data['password'],
                        mf=data['mf'],
                        status='PENDING',
                    )
            finally:
                connection.set_schema(current_schema)
            messages.success(request, 'Paramètres elfatoora mis à jour.')
            return redirect('elfatoora_settings')
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        initial = {}
        if account:
            initial = {'username': account.username, 'mf': account.mf}
        form = ElfatooraAccountForm(initial=initial)

    return render(request, 'sales/elfatoora_settings.html', {
        'form': form,
        'account': account,
    })


def company_logo(request):
    """Serve the company logo stored as a base64 data URL."""
    import base64 as _b64, re
    from django.http import Http404
    obj = Settings.get_cached()
    if not obj or not obj.clientLogo:
        raise Http404
    match = re.match(r'data:([^;]+);base64,(.+)', obj.clientLogo, re.DOTALL)
    if not match:
        raise Http404
    content_type = match.group(1)
    image_data = _b64.b64decode(match.group(2))
    response = HttpResponse(image_data, content_type=content_type)
    response['Cache-Control'] = 'private, max-age=86400'
    return response


# ---------------------------------------------------------------------------
# Avoirs (Factures d'Avoir / Credit Notes)
# ---------------------------------------------------------------------------

@login_required
def avoirs_list(request):
    """List all credit notes with pagination and filters."""
    avoirs = CreditNote.objects.all().select_related('client', 'invoice').order_by('-date_created')
    clients = Client.objects.all().order_by('clientname')
    settings_obj = Settings.get_cached()

    search = request.GET.get('search', '').strip()
    client_id = request.GET.get('client', '').strip()

    if search:
        avoirs = avoirs.filter(
            Q(uniqueId__icontains=search) | Q(client__clientname__icontains=search) | Q(description__icontains=search)
        )
    if client_id:
        avoirs = avoirs.filter(client_id=client_id)

    paginator = Paginator(avoirs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'sales/avoirs.html', {
        'avoirs': page_obj,
        'clients': clients,
        'settings_obj': settings_obj,
        'search_query': search,
        'selected_client': client_id,
    })


@login_required
def avoir_create(request):
    """Create a new credit note and post a CREDIT ledger entry."""
    if request.method != 'POST':
        return redirect('avoirs_list')

    try:
        with transaction.atomic():
            client_id = request.POST.get('client')
            if not client_id:
                messages.error(request, 'Client requis.')
                return redirect('avoirs_list')

            client = get_object_or_404(Client, id=client_id)

            description = request.POST.get('description', '').strip()
            if not description:
                messages.error(request, 'La description est requise.')
                return redirect('avoirs_list')

            amount_ht_raw = request.POST.get('amount_ht', '').strip()
            if not amount_ht_raw:
                messages.error(request, 'Le montant HT est requis.')
                return redirect('avoirs_list')
            amount_ht = Decimal(amount_ht_raw)

            # TVA: use submitted value or fall back to Settings
            tva_raw = request.POST.get('tva', '').strip()
            if tva_raw:
                tva = Decimal(tva_raw)
            else:
                s = Settings.get_cached()
                tva = Decimal(str(s.tva)) if s and s.tva else Decimal('19.00')

            # Optional linked invoice
            invoice_id = request.POST.get('invoice_id', '').strip()
            linked_invoice = None
            if invoice_id:
                try:
                    linked_invoice = Invoice.objects.get(id=invoice_id, client=client)
                except Invoice.DoesNotExist:
                    pass

            from datetime import datetime, time
            from django.utils import timezone as dj_tz

            custom_date_raw = request.POST.get('invoice_date', '').strip()
            custom_datetime = None
            if custom_date_raw:
                try:
                    parsed = datetime.strptime(custom_date_raw, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError('Date invalide')
                tz = dj_tz.get_current_timezone()
                custom_datetime = dj_tz.make_aware(datetime.combine(parsed, time.min), tz)

            custom_number_raw = request.POST.get('invoice_number', '').strip()
            manual_number = None
            if custom_number_raw:
                try:
                    manual_number = int(custom_number_raw)
                except ValueError:
                    raise ValueError('Numéro invalide (1–999)')

            year = (custom_datetime.year if custom_datetime
                    else dj_tz.localtime(dj_tz.now()).year)
            unique_id = CreditNote.generate_unique_id(year, manual_number=manual_number)

            cn_kwargs = dict(
                client=client,
                invoice=linked_invoice,
                description=description,
                amount_ht=amount_ht,
                tva=tva,
                uniqueId=unique_id,
            )
            if custom_datetime is not None:
                cn_kwargs['date_created'] = custom_datetime
            credit_note = CreditNote.objects.create(**cn_kwargs)

            ClientTransaction.objects.create(
                client=client,
                credit_note=credit_note,
                invoice=credit_note.invoice,
                transaction_type='CREDIT',
                source='AVOIR_CREATED',
                amount=credit_note.calculate_total(),
                description=f'Avoir {credit_note.uniqueId}',
            )

            messages.success(request, f'Avoir {credit_note.uniqueId} créé avec succès.')
            return redirect('avoir_detail', credit_note.id)

    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Erreur lors de la création: {str(e)}')

    return redirect('avoirs_list')


@login_required
def avoir_edit(request, avoir_id):
    """Edit a credit note and update its CREDIT ledger entry."""
    credit_note = get_object_or_404(CreditNote, id=avoir_id)
    next_page = request.POST.get('next', 'detail')

    if request.method != 'POST':
        return redirect('avoir_detail', avoir_id)

    try:
        with transaction.atomic():
            description = request.POST.get('description', '').strip()
            if not description:
                raise ValueError('La description est requise.')

            amount_ht_raw = request.POST.get('amount_ht', '').strip()
            if not amount_ht_raw:
                raise ValueError('Le montant HT est requis.')
            credit_note.amount_ht = Decimal(amount_ht_raw)

            tva_raw = request.POST.get('tva', '').strip()
            if tva_raw:
                credit_note.tva = Decimal(tva_raw)

            credit_note.description = description

            # Optional linked invoice (must belong to same client)
            invoice_id = request.POST.get('invoice_id', '').strip()
            if invoice_id:
                try:
                    credit_note.invoice = Invoice.objects.get(id=invoice_id, client=credit_note.client)
                except Invoice.DoesNotExist:
                    credit_note.invoice = None
            else:
                credit_note.invoice = None

            from datetime import datetime, time
            from django.utils import timezone as dj_tz

            custom_date_raw = request.POST.get('invoice_date', '').strip()
            if custom_date_raw:
                try:
                    parsed = datetime.strptime(custom_date_raw, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError('Date invalide')
                tz = dj_tz.get_current_timezone()
                credit_note.date_created = dj_tz.make_aware(
                    datetime.combine(parsed, time.min), tz
                )

            custom_number_raw = request.POST.get('invoice_number', '').strip()
            if custom_number_raw:
                try:
                    manual_number = int(custom_number_raw)
                except ValueError:
                    raise ValueError('Numéro invalide (1–999)')
                year = credit_note.date_created.year if credit_note.date_created else dj_tz.now().year
                credit_note.uniqueId = CreditNote.generate_unique_id(
                    year, manual_number=manual_number, exclude_pk=credit_note.pk,
                )

            credit_note.save()

            # Update the matching CREDIT ledger entry
            ledger_entry = ClientTransaction.objects.filter(
                credit_note=credit_note,
                source='AVOIR_CREATED',
                transaction_type='CREDIT',
            ).first()

            new_total = credit_note.calculate_total()
            if ledger_entry:
                ledger_entry.amount = new_total
                ledger_entry.invoice = credit_note.invoice
                ledger_entry.save()
            else:
                ClientTransaction.objects.create(
                    client=credit_note.client,
                    credit_note=credit_note,
                    invoice=credit_note.invoice,
                    transaction_type='CREDIT',
                    source='AVOIR_CREATED',
                    amount=new_total,
                    description=f'Avoir {credit_note.uniqueId}',
                )

            messages.success(request, f'Avoir {credit_note.uniqueId} modifié avec succès.')

    except (ValueError, TypeError) as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Erreur lors de la modification: {str(e)}')

    if next_page == 'detail':
        return redirect('avoir_detail', avoir_id)
    return redirect('avoirs_list')


@login_required
def avoir_delete(request, avoir_id):
    """Delete a credit note and post a DEBIT reversal to the ledger."""
    credit_note = get_object_or_404(CreditNote, id=avoir_id)

    if request.method != 'POST':
        return redirect('avoirs_list')

    try:
        with transaction.atomic():
            ClientTransaction.objects.create(
                client=credit_note.client,
                credit_note=credit_note,
                invoice=credit_note.invoice,
                transaction_type='DEBIT',
                source='AVOIR_DELETED',
                amount=credit_note.calculate_total(),
                description=f'Annulation avoir {credit_note.uniqueId}',
            )
            unique_id = credit_note.uniqueId
            credit_note.delete()
            messages.success(request, f'Avoir {unique_id} supprimé.')
    except Exception as e:
        messages.error(request, f'Erreur lors de la suppression: {str(e)}')

    return redirect('avoirs_list')


@login_required
def avoir_detail(request, avoir_id):
    """Display a printable credit note detail page."""
    from gov.models import GovInvoice
    credit_note = get_object_or_404(CreditNote, id=avoir_id)
    settings_obj = Settings.get_cached()
    total_in_words = num2words_tnd_fr(Decimal(str(credit_note.calculate_total())))
    return render(request, 'sales/avoir_detail.html', {
        'avoir': credit_note,
        'settings_obj': settings_obj,
        'total_in_words': total_in_words,
        'gov_invoice': GovInvoice.objects.filter(credit_note=credit_note).first(),
    })


@login_required
def avoir_modal_data(request, avoir_id):
    """Return JSON data for populating the edit modal."""
    credit_note = get_object_or_404(CreditNote, id=avoir_id)
    return JsonResponse({
        'id': credit_note.id,
        'client_id': credit_note.client_id,
        'invoice_id': credit_note.invoice_id or '',
        'description': credit_note.description,
        'amount_ht': str(credit_note.amount_ht),
        'tva': str(credit_note.tva),
        'uniqueId': credit_note.uniqueId,
    })


@login_required
def client_all_invoices(request, client_id):
    """Return JSON list of all invoices for a client (for the avoir link dropdown)."""
    client = get_object_or_404(Client, id=client_id)
    invoices = Invoice.objects.filter(client=client).order_by('-date_created').values(
        'id', 'uniqueId', 'date_created'
    )
    data = [
        {
            'id': inv['id'],
            'uniqueId': inv['uniqueId'],
            'date': inv['date_created'].strftime('%d/%m/%Y') if inv['date_created'] else '',
        }
        for inv in invoices
    ]
    return JsonResponse(data, safe=False)


# ─── Bons de Livraison ───────────────────────────────────────────────────────

@login_required
def bons_livraison_list(request):
    bons = BonLivraison.objects.all().select_related('client').prefetch_related('lines').order_by('-date_created')

    search = request.GET.get('search', '').strip()
    client_id = request.GET.get('client', '').strip()
    status = request.GET.get('status', '').strip()

    if search:
        bons = bons.filter(
            Q(uniqueId__icontains=search) | Q(client__clientname__icontains=search)
        )
    if client_id:
        bons = bons.filter(client_id=client_id)
    if status:
        bons = bons.filter(status=status)

    paginator = Paginator(bons, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    settings_obj = Settings.get_cached()
    clients = Client.objects.all().order_by('clientname')
    default_tva = Decimal(str(settings_obj.tva)) if settings_obj and settings_obj.tva else Decimal('19.00')

    return render(request, 'sales/bons_livraison.html', {
        'bons': page_obj,
        'clients': clients,
        'settings_obj': settings_obj,
        'search_query': search,
        'selected_client': client_id,
        'selected_status': status,
        'count': bons.count(),
        'default_tva': default_tva,
    })


@login_required
def bon_livraison_modal_data(request, bon_id):
    bon = get_object_or_404(BonLivraison, id=bon_id)
    lines = [
        {'id': l.id, 'description': l.description, 'amount': str(l.amount)}
        for l in bon.lines.all()
    ]
    return JsonResponse({
        'id': bon.id,
        'client_id': bon.client_id or '',
        'status': bon.status,
        'tva': str(bon.tva),
        'notes': bon.notes or '',
        'uniqueId': bon.uniqueId,
        'lines': lines,
    })


@login_required
@require_POST
def bon_livraison_create(request):
    client_id = request.POST.get('client', '').strip()
    tva_raw = request.POST.get('tva', '19.000').strip() or '19.000'
    notes = request.POST.get('notes', '').strip()
    status = request.POST.get('status', 'DRAFT')
    descriptions = request.POST.getlist('description[]')
    amounts = request.POST.getlist('amount[]')

    client = get_object_or_404(Client, id=client_id) if client_id else None

    try:
        bon = BonLivraison.objects.create(
            client=client,
            tva=Decimal(tva_raw),
            notes=notes,
            status=status,
        )
        for desc, amt in zip(descriptions, amounts):
            desc, amt = desc.strip(), amt.strip()
            if desc and amt:
                BonLivraisonLine.objects.create(bon=bon, description=desc, amount=Decimal(amt))
        messages.success(request, f'Bon de livraison {bon.uniqueId} créé avec succès.')
    except Exception as e:
        messages.error(request, f'Erreur lors de la création : {e}')

    return redirect('bons_livraison_list')


@login_required
@require_POST
def bon_livraison_edit(request, bon_id):
    bon = get_object_or_404(BonLivraison, id=bon_id)
    client_id = request.POST.get('client', '').strip()
    tva_raw = request.POST.get('tva', '19.000').strip() or '19.000'
    notes = request.POST.get('notes', '').strip()
    status = request.POST.get('status', 'DRAFT')
    descriptions = request.POST.getlist('description[]')
    amounts = request.POST.getlist('amount[]')

    try:
        bon.client = get_object_or_404(Client, id=client_id) if client_id else None
        bon.tva = Decimal(tva_raw)
        bon.notes = notes
        bon.status = status
        bon.save()

        bon.lines.all().delete()
        for desc, amt in zip(descriptions, amounts):
            desc, amt = desc.strip(), amt.strip()
            if desc and amt:
                BonLivraisonLine.objects.create(bon=bon, description=desc, amount=Decimal(amt))
        messages.success(request, f'Bon de livraison {bon.uniqueId} modifié avec succès.')
    except Exception as e:
        messages.error(request, f'Erreur lors de la modification : {e}')

    return redirect('bons_livraison_list')


@login_required
@require_POST
def bon_livraison_delete(request, bon_id):
    bon = get_object_or_404(BonLivraison, id=bon_id)
    uid = bon.uniqueId
    bon.delete()
    messages.success(request, f'Bon de livraison {uid} supprimé.')
    return redirect('bons_livraison_list')


@login_required
def bon_livraison_detail(request, bon_id):
    bon = get_object_or_404(
        BonLivraison.objects.select_related('client').prefetch_related('lines'),
        id=bon_id,
    )
    settings_obj = Settings.get_cached()
    total_in_words = num2words_tnd_fr(Decimal(str(bon.calculate_total_ttc())))
    return render(request, 'sales/bon_livraison_detail.html', {
        'bon': bon,
        'settings_obj': settings_obj,
        'total_in_words': total_in_words,
    })


# ─────────────────────────────────────────────
# DEVIS (Quotes / Approximation Invoices)
# ─────────────────────────────────────────────

@login_required
def devis_list(request):
    devis_qs = Devis.objects.select_related('client', 'converted_invoice').all().order_by('-date_created')

    search = request.GET.get('search', '').strip()
    client_id = request.GET.get('client', '').strip()
    status = request.GET.get('status', '').strip()

    if search:
        devis_qs = devis_qs.filter(
            Q(uniqueId__icontains=search) | Q(client__clientname__icontains=search) | Q(title__icontains=search)
        )
    if client_id:
        devis_qs = devis_qs.filter(client_id=client_id)
    if status:
        devis_qs = devis_qs.filter(status=status)

    paginator = Paginator(devis_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'sales/devis_list.html', {
        'devis_list': page_obj,
        'clients': Client.objects.all(),
        'services': Service.objects.all(),
        'settings': Settings.get_cached(),
        'search_query': search,
        'selected_client': client_id,
        'selected_status': status,
    })


@login_required
def devis_create(request):
    if request.method != 'POST':
        return redirect('devis_list')

    try:
        with transaction.atomic():
            client_id = request.POST.get('client')
            if not client_id:
                messages.error(request, 'Client requis.')
                return redirect('devis_list')

            client = get_object_or_404(Client, id=client_id)
            title = request.POST.get('title', '').strip()
            notes = request.POST.get('notes', '').strip()
            settings = Settings.get_cached()

            tva_input = request.POST.get('tva', '').strip()
            tva = Decimal(tva_input) if tva_input else (
                Decimal(str(settings.tva)) if settings and settings.tva else Decimal('19.00')
            )

            timbre_input = request.POST.get('timbre_fiscal', '').strip()
            timbre_fiscal = Decimal(timbre_input) if timbre_input else (
                Decimal(str(settings.dt)) if settings and settings.dt else Decimal('1.000')
            )

            discount = Decimal(request.POST.get('discount', '0') or '0')

            service_ids = request.POST.getlist('service_id[]')
            if not service_ids:
                messages.error(request, 'Vous devez ajouter au moins un service.')
                return redirect('devis_list')

            devis = Devis.objects.create(
                client=client,
                title=title,
                notes=notes,
                tva=tva,
                timbre_fiscal=timbre_fiscal,
                discount=discount,
            )

            fodec_flags = request.POST.getlist('has_fodec[]')
            unit_prices = request.POST.getlist('unit_price[]')
            hours_list = request.POST.getlist('hours_used[]')
            days_list = request.POST.getlist('days_used[]')
            units_list = request.POST.getlist('units_used[]')

            for i, service_id in enumerate(service_ids):
                if not service_id:
                    continue
                service = get_object_or_404(Service, id=service_id)
                has_fodec = fodec_flags[i] == '1' if i < len(fodec_flags) else False
                price = Decimal(str(unit_prices[i])) if i < len(unit_prices) and unit_prices[i] else service.price

                InvoiceService.objects.create(
                    devis=devis,
                    service=service,
                    unit_price=price,
                    has_fodec=has_fodec,
                    hours_used=int(hours_list[i]) if i < len(hours_list) and hours_list[i] else None,
                    days_used=int(days_list[i]) if i < len(days_list) and days_list[i] else None,
                    units_used=int(units_list[i]) if i < len(units_list) and units_list[i] else None,
                )

            messages.success(request, f'Devis {devis.uniqueId} créé avec succès.')
            return redirect('devis_detail', devis.id)

    except Exception as e:
        messages.error(request, f'Erreur: {str(e)}')
    return redirect('devis_list')


@login_required
def devis_detail(request, devis_id):
    devis = get_object_or_404(
        Devis.objects.select_related('client', 'converted_invoice')
                     .prefetch_related('devis_services__service'),
        id=devis_id
    )
    total_in_words = num2words_tnd_fr(Decimal(str(devis.calculate_total())))
    return render(request, 'sales/devis_detail.html', {
        'devis': devis,
        'settings': Settings.get_cached(),
        'clients': Client.objects.all(),
        'services': Service.objects.all(),
        'total_in_words': total_in_words,
    })


@login_required
def devis_update(request, devis_id):
    devis = get_object_or_404(Devis, id=devis_id)

    if request.method != 'POST':
        return redirect('devis_detail', devis_id)

    try:
        with transaction.atomic():
            client_id = request.POST.get('client')
            if client_id:
                devis.client = get_object_or_404(Client, id=client_id)

            devis.title = request.POST.get('title', '').strip()
            devis.notes = request.POST.get('notes', '').strip()

            tva_input = request.POST.get('tva', '').strip()
            if tva_input:
                devis.tva = Decimal(tva_input)

            timbre_input = request.POST.get('timbre_fiscal', '').strip()
            if timbre_input:
                devis.timbre_fiscal = Decimal(timbre_input)

            devis.discount = Decimal(request.POST.get('discount', '0') or '0')

            status = request.POST.get('status', '').strip()
            if status in ('PENDING', 'REJECTED'):
                devis.status = status

            devis.save()

            service_ids = request.POST.getlist('service_id[]')
            if service_ids:
                devis.devis_services.all().delete()
                fodec_flags = request.POST.getlist('has_fodec[]')
                unit_prices = request.POST.getlist('unit_price[]')
                hours_list = request.POST.getlist('hours_used[]')
                days_list = request.POST.getlist('days_used[]')
                units_list = request.POST.getlist('units_used[]')

                for i, service_id in enumerate(service_ids):
                    if not service_id:
                        continue
                    service = get_object_or_404(Service, id=service_id)
                    has_fodec = fodec_flags[i] == '1' if i < len(fodec_flags) else False
                    price = Decimal(str(unit_prices[i])) if i < len(unit_prices) and unit_prices[i] else service.price

                    InvoiceService.objects.create(
                        devis=devis,
                        service=service,
                        unit_price=price,
                        has_fodec=has_fodec,
                        hours_used=int(hours_list[i]) if i < len(hours_list) and hours_list[i] else None,
                        days_used=int(days_list[i]) if i < len(days_list) and days_list[i] else None,
                        units_used=int(units_list[i]) if i < len(units_list) and units_list[i] else None,
                    )

            messages.success(request, f'Devis {devis.uniqueId} mis à jour.')
            return redirect('devis_detail', devis.id)

    except Exception as e:
        messages.error(request, f'Erreur: {str(e)}')
    return redirect('devis_detail', devis_id)


@login_required
def devis_delete(request, devis_id):
    devis = get_object_or_404(Devis, id=devis_id)
    if request.method == 'POST':
        uid = devis.uniqueId
        devis.delete()
        messages.success(request, f'Devis {uid} supprimé.')
        return redirect('devis_list')
    return render(request, 'sales/devis_delete.html', {'devis': devis})


@login_required
def devis_convert(request, devis_id):
    """Convert a PENDING devis to an Invoice. POST only."""
    devis = get_object_or_404(Devis, id=devis_id)

    if request.method != 'POST':
        return redirect('devis_detail', devis_id)

    if devis.converted_invoice:
        messages.info(request, f'Ce devis a déjà été converti en {devis.converted_invoice.uniqueId}.')
        return redirect('invoice_detail', devis.converted_invoice.id)

    try:
        with transaction.atomic():
            invoice = devis.convert_to_invoice()
            messages.success(request, f'Devis {devis.uniqueId} converti en facture {invoice.uniqueId}.')
            return redirect('invoice_detail', invoice.id)
    except Exception as e:
        messages.error(request, f'Erreur lors de la conversion: {str(e)}')
        return redirect('devis_detail', devis_id)


@login_required
@require_POST
def invoice_ngsign_submit(request, invoice_id):
    """Submit an invoice to NGSign asynchronously."""
    import threading
    from django.db import connection
    from django.utils import timezone
    from gov.models import GovInvoice

    invoice = get_object_or_404(Invoice, id=invoice_id)

    gov_invoice = GovInvoice.objects.filter(invoice=invoice).first()

    # Guard: block if already submitting
    if gov_invoice and gov_invoice.ngsign_status == 'SUBMITTING':
        return JsonResponse({
            'success': False,
            'error': 'Soumission déjà en cours.'
        }, status=409)

    # Create or update GovInvoice
    if gov_invoice:
        gov_invoice.ngsign_status = 'SUBMITTING'
        gov_invoice.status = 'draft'
        gov_invoice.submitted_at = timezone.now()
        gov_invoice.notes = ''
        gov_invoice.save(update_fields=['ngsign_status', 'status', 'submitted_at', 'notes'])
    else:
        gov_invoice = GovInvoice.objects.create(
            invoice=invoice,
            unsigned_xml=b'',
            status='draft',
            ngsign_status='SUBMITTING',
            submitted_at=timezone.now(),
        )

    schema_name = connection.schema_name
    redirect_url = request.build_absolute_uri(reverse('invoice_detail', args=[invoice.id]))
    thread = threading.Thread(
        target=_process_ngsign_submission,
        args=(gov_invoice.id, schema_name, redirect_url),
        daemon=True,
    )
    thread.start()

    return JsonResponse({
        'success': True,
        'message': 'Document soumis en arrière-plan.'
    })


@login_required
@require_POST
def invoice_ngsign_check(request, invoice_id):
    """Force TTN status check for an invoice."""
    from gov.models import GovInvoice
    from gov.ngsign.service import check_status
    from gov.ngsign.exceptions import NGSignAPIError, NGSignNotConfiguredError

    invoice = get_object_or_404(Invoice, id=invoice_id)
    gov_invoice = GovInvoice.objects.filter(invoice=invoice).first()

    if not gov_invoice or not gov_invoice.ngsign_invoice_uuid:
        return JsonResponse({
            'success': False,
            'error': "Cette facture n'a pas encore été soumise à NGSign."
        }, status=400)

    try:
        result = check_status(gov_invoice)
        return JsonResponse({
            'success': True,
            'ngsign_status': gov_invoice.ngsign_status,
            'ttn_reference': result.get('ttnReference', ''),
        })
    except (NGSignAPIError, NGSignNotConfiguredError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def avoir_ngsign_submit(request, avoir_id):
    """Submit a credit note (avoir) to NGSign asynchronously."""
    import threading
    from django.db import connection
    from django.utils import timezone
    from gov.models import GovInvoice
    from sales.models import CreditNote

    credit_note = get_object_or_404(CreditNote, id=avoir_id)

    gov_invoice = GovInvoice.objects.filter(credit_note=credit_note).first()

    # Guard: block if already submitting
    if gov_invoice and gov_invoice.ngsign_status == 'SUBMITTING':
        return JsonResponse({
            'success': False,
            'error': 'Soumission déjà en cours.'
        }, status=409)

    # Create or update GovInvoice
    if gov_invoice:
        gov_invoice.ngsign_status = 'SUBMITTING'
        gov_invoice.status = 'draft'
        gov_invoice.submitted_at = timezone.now()
        gov_invoice.notes = ''
        gov_invoice.save(update_fields=['ngsign_status', 'status', 'submitted_at', 'notes'])
    else:
        gov_invoice = GovInvoice.objects.create(
            credit_note=credit_note,
            unsigned_xml=b'',
            status='draft',
            ngsign_status='SUBMITTING',
            submitted_at=timezone.now(),
        )

    schema_name = connection.schema_name
    redirect_url = request.build_absolute_uri(reverse('avoir_detail', args=[credit_note.id]))
    thread = threading.Thread(
        target=_process_ngsign_submission,
        args=(gov_invoice.id, schema_name, redirect_url),
        daemon=True,
    )
    thread.start()

    return JsonResponse({
        'success': True,
        'message': 'Document soumis en arrière-plan.'
    })


@login_required
@require_POST
def avoir_ngsign_check(request, avoir_id):
    """Force TTN status check for a credit note."""
    from gov.models import GovInvoice
    from gov.ngsign.service import check_status
    from gov.ngsign.exceptions import NGSignAPIError, NGSignNotConfiguredError
    from sales.models import CreditNote

    credit_note = get_object_or_404(CreditNote, id=avoir_id)
    gov_invoice = GovInvoice.objects.filter(credit_note=credit_note).first()

    if not gov_invoice or not gov_invoice.ngsign_invoice_uuid:
        return JsonResponse({
            'success': False,
            'error': "Cet avoir n'a pas encore été soumis à NGSign."
        }, status=400)

    try:
        result = check_status(gov_invoice)
        return JsonResponse({
            'success': True,
            'ngsign_status': gov_invoice.ngsign_status,
            'ttn_reference': result.get('ttnReference', ''),
        })
    except (NGSignAPIError, NGSignNotConfiguredError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def invoice_elfatoora_submit(request, invoice_id):
    """Push signed XML of an invoice to TTN via elfatoora SOAP."""
    from gov.models import GovInvoice
    from gov.elfatoora.service import submit, ElfatooraNotReadyError, ElfatooraNotConfiguredError
    from gov.elfatoora.client import ElfatooraError

    invoice = get_object_or_404(Invoice, id=invoice_id)
    gov_invoice = GovInvoice.objects.filter(invoice=invoice).first()

    if not gov_invoice or not gov_invoice.signed_xml:
        return JsonResponse({
            'success': False,
            'error': "Cette facture n'a pas encore été signée."
        }, status=400)

    if gov_invoice.elfatoora_generated_ref:
        return JsonResponse({
            'success': False,
            'error': "Cette facture a déjà été transmise à TTN.",
            'generated_ref': gov_invoice.elfatoora_generated_ref,
        }, status=409)

    try:
        ref = submit(gov_invoice)
        return JsonResponse({
            'success': True,
            'generated_ref': ref,
            'elfatoora_status': gov_invoice.elfatoora_status,
        })
    except (ElfatooraError, ElfatooraNotReadyError, ElfatooraNotConfiguredError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def invoice_elfatoora_poll(request, invoice_id):
    """Query TTN for acknowledgements of a previously submitted invoice."""
    from gov.models import GovInvoice
    from gov.elfatoora.service import poll, ElfatooraNotReadyError, ElfatooraNotConfiguredError
    from gov.elfatoora.client import ElfatooraError

    invoice = get_object_or_404(Invoice, id=invoice_id)
    gov_invoice = GovInvoice.objects.filter(invoice=invoice).first()

    if not gov_invoice or not gov_invoice.elfatoora_generated_ref:
        return JsonResponse({
            'success': False,
            'error': "Cette facture n'a pas encore été transmise à TTN."
        }, status=400)

    try:
        poll(gov_invoice)
        return JsonResponse({
            'success': True,
            'elfatoora_status': gov_invoice.elfatoora_status,
            'last_error': gov_invoice.elfatoora_last_error,
        })
    except (ElfatooraError, ElfatooraNotReadyError, ElfatooraNotConfiguredError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def avoir_elfatoora_submit(request, avoir_id):
    """Push signed XML of a credit note to TTN via elfatoora SOAP."""
    from gov.models import GovInvoice
    from gov.elfatoora.service import submit, ElfatooraNotReadyError, ElfatooraNotConfiguredError
    from gov.elfatoora.client import ElfatooraError
    from sales.models import CreditNote

    credit_note = get_object_or_404(CreditNote, id=avoir_id)
    gov_invoice = GovInvoice.objects.filter(credit_note=credit_note).first()

    if not gov_invoice or not gov_invoice.signed_xml:
        return JsonResponse({
            'success': False,
            'error': "Cet avoir n'a pas encore été signé."
        }, status=400)

    if gov_invoice.elfatoora_generated_ref:
        return JsonResponse({
            'success': False,
            'error': "Cet avoir a déjà été transmis à TTN.",
            'generated_ref': gov_invoice.elfatoora_generated_ref,
        }, status=409)

    try:
        ref = submit(gov_invoice)
        return JsonResponse({
            'success': True,
            'generated_ref': ref,
            'elfatoora_status': gov_invoice.elfatoora_status,
        })
    except (ElfatooraError, ElfatooraNotReadyError, ElfatooraNotConfiguredError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def avoir_elfatoora_poll(request, avoir_id):
    """Query TTN for acknowledgements of a previously submitted credit note."""
    from gov.models import GovInvoice
    from gov.elfatoora.service import poll, ElfatooraNotReadyError, ElfatooraNotConfiguredError
    from gov.elfatoora.client import ElfatooraError
    from sales.models import CreditNote

    credit_note = get_object_or_404(CreditNote, id=avoir_id)
    gov_invoice = GovInvoice.objects.filter(credit_note=credit_note).first()

    if not gov_invoice or not gov_invoice.elfatoora_generated_ref:
        return JsonResponse({
            'success': False,
            'error': "Cet avoir n'a pas encore été transmis à TTN."
        }, status=400)

    try:
        poll(gov_invoice)
        return JsonResponse({
            'success': True,
            'elfatoora_status': gov_invoice.elfatoora_status,
            'last_error': gov_invoice.elfatoora_last_error,
        })
    except (ElfatooraError, ElfatooraNotReadyError, ElfatooraNotConfiguredError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _process_ngsign_submission(gov_invoice_id, schema_name, redirect_url=None):
    """
    Background thread: generate XML/PDF, submit to NGSign, update GovInvoice.
    Runs outside the request cycle — must set tenant schema and close connection.
    """
    import logging
    from django.db import connection
    from django.utils import timezone

    logger = logging.getLogger(__name__)

    try:
        connection.set_schema(schema_name)
        from gov.models import GovInvoice
        from gov.ngsign.service import submit_invoice
        from gov.teif.builder import build_unsigned_teif, build_unsigned_teif_avoir
        from sales.models import Settings

        gov_invoice = GovInvoice.objects.get(id=gov_invoice_id)
        seller = Settings.get_cached()

        # Generate unsigned XML if missing
        if not gov_invoice.unsigned_xml:
            if gov_invoice.credit_note:
                gov_invoice.unsigned_xml = build_unsigned_teif_avoir(gov_invoice.credit_note, seller)
            else:
                gov_invoice.unsigned_xml = build_unsigned_teif(gov_invoice.invoice, seller)
            gov_invoice.save(update_fields=['unsigned_xml'])

        submit_invoice(gov_invoice, redirect_url=redirect_url)
        logger.info(f'NGSign submission succeeded for GovInvoice {gov_invoice_id}')

    except Exception as e:
        logger.exception(f'NGSign submission failed for GovInvoice {gov_invoice_id}')
        try:
            from gov.models import GovInvoice
            gov_invoice = GovInvoice.objects.get(id=gov_invoice_id)
            gov_invoice.ngsign_status = 'ERROR'
            gov_invoice.notes = str(e)[:500]
            gov_invoice.save(update_fields=['ngsign_status', 'notes'])
        except Exception:
            logger.exception(f'Failed to update error status for GovInvoice {gov_invoice_id}')
    finally:
        connection.close()


@login_required
@require_GET
def ngsign_pending_api(request):
    """Return all GovInvoice records with non-terminal ngsign_status, grouped by category."""
    from django.urls import reverse
    from django.utils import timezone
    from gov.models import GovInvoice
    from gov.ngsign.client import get_pds_url
    from .models import NotificationState

    TO_SIGN = {'CREATED', 'CONFIGURED'}
    ERRORS = {'ERROR', 'TTN_REJECTED', 'TTN_NOTTRANSFERED'}
    STALE_SECONDS = 60

    # NOTE: This endpoint is polled by every client every 30s (see base.html).
    # It MUST stay a cheap DB-only read. Refreshing status from NGSign here did
    # synchronous external HTTP (TIMEOUT=30s) per in-flight invoice, which
    # starved gunicorn workers and made the whole site slow on prod. Status
    # refresh now lives in the `refresh_ngsign` management command (cron).

    gov_invoices = (
        GovInvoice.objects
        .exclude(ngsign_status__in=['TTN_SIGNED', 'TTN_TRANSFERED', 'CANCELLED'])
        .exclude(ngsign_status__isnull=True)
        .exclude(ngsign_status='')
        .select_related('invoice__client', 'credit_note__client')
    )

    # Prefetch notification states for current user
    user_states = {
        ns.gov_invoice_id: ns
        for ns in NotificationState.objects.filter(
            user=request.user,
            gov_invoice__in=gov_invoices,
        )
    }

    now = timezone.now()
    to_sign = []
    errors = []
    in_progress = []
    unread_count = 0

    for gi in gov_invoices:
        if gi.invoice:
            doc_type = 'invoice'
            doc_number = gi.invoice.uniqueId
            client_name = gi.invoice.client.clientname if gi.invoice.client else ''
            detail_url = reverse('invoice_detail', args=[gi.invoice.id])
        elif gi.credit_note:
            doc_type = 'avoir'
            doc_number = gi.credit_note.uniqueId
            client_name = gi.credit_note.client.clientname if gi.credit_note.client else ''
            detail_url = reverse('avoir_detail', args=[gi.credit_note.id])
        else:
            continue

        # Stale detection: SUBMITTING for >60s is treated as ERROR
        status = gi.ngsign_status
        if status == 'SUBMITTING' and gi.submitted_at and (now - gi.submitted_at).total_seconds() > STALE_SECONDS:
            status = 'ERROR'
            gi.ngsign_status = 'ERROR'
            gi.notes = 'Soumission expirée (délai dépassé).'
            gi.save(update_fields=['ngsign_status', 'notes'])

        # Check notification state
        state = user_states.get(gi.id)
        is_read = False
        if state:
            if state.status_snapshot == status:
                # Status unchanged — respect saved state
                if state.is_dismissed:
                    continue  # Skip dismissed items
                is_read = state.is_read
            else:
                # Status changed — reset stale state
                state.is_read = False
                state.is_dismissed = False
                state.dismissed_at = None
                state.status_snapshot = status
                state.save(update_fields=['is_read', 'is_dismissed', 'dismissed_at', 'status_snapshot'])

        if not is_read:
            unread_count += 1

        item = {
            'id': gi.id,
            'doc_type': doc_type,
            'doc_number': doc_number,
            'client_name': client_name,
            'status': status,
            'detail_url': detail_url,
            'pds_url': get_pds_url(gi.ngsign_transaction_uuid) if gi.ngsign_transaction_uuid else None,
            'notes': gi.notes or '',
            'is_read': is_read,
        }

        if status in TO_SIGN:
            to_sign.append(item)
        elif status in ERRORS:
            errors.append(item)
        else:
            in_progress.append(item)

    return JsonResponse({
        'to_sign': to_sign,
        'errors': errors,
        'in_progress': in_progress,
        'total': len(to_sign) + len(errors) + len(in_progress),
        'unread_count': unread_count,
    })


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all active (non-terminal, non-dismissed) notifications as read for the current user."""
    from gov.models import GovInvoice
    from .models import NotificationState

    TERMINAL = {'TTN_SIGNED', 'TTN_TRANSFERED', 'CANCELLED'}

    active_govs = (
        GovInvoice.objects
        .exclude(ngsign_status__in=TERMINAL)
        .exclude(ngsign_status__isnull=True)
        .exclude(ngsign_status='')
    )

    for gi in active_govs:
        state, _ = NotificationState.objects.get_or_create(
            user=request.user,
            gov_invoice=gi,
            defaults={'status_snapshot': gi.ngsign_status, 'is_read': True},
        )
        if not _:
            # Only update if not currently dismissed with matching status
            if state.is_dismissed and state.status_snapshot == gi.ngsign_status:
                continue
            state.is_read = True
            state.status_snapshot = gi.ngsign_status
            state.save(update_fields=['is_read', 'status_snapshot'])

    return JsonResponse({'ok': True, 'unread_count': 0})


@login_required
@require_POST
def dismiss_notification(request, gov_invoice_id):
    """Dismiss a single notification by GovInvoice ID."""
    from gov.models import GovInvoice
    from .models import NotificationState

    gi = get_object_or_404(GovInvoice, id=gov_invoice_id)

    NotificationState.objects.update_or_create(
        user=request.user,
        gov_invoice=gi,
        defaults={
            'is_dismissed': True,
            'status_snapshot': gi.ngsign_status,
            'dismissed_at': timezone.now(),
        },
    )

    return JsonResponse({'ok': True})


@login_required
def notifications_page(request):
    """Full notifications history page with filtering and pagination."""
    from gov.models import GovInvoice
    from .models import NotificationState

    STATUS_TABS = {
        'to_sign': {'CREATED', 'CONFIGURED'},
        'errors': {'ERROR', 'TTN_REJECTED', 'TTN_NOTTRANSFERED'},
        'in_progress': {'SUBMITTING', 'SIGNED', 'MIXED'},
        'done': {'TTN_SIGNED', 'TTN_TRANSFERED', 'CANCELLED'},
    }

    active_tab = request.GET.get('tab', 'all')

    govs = (
        GovInvoice.objects
        .exclude(ngsign_status__isnull=True)
        .exclude(ngsign_status='')
        .select_related('invoice__client', 'credit_note__client')
        .order_by('-created_at')
    )

    if active_tab in STATUS_TABS:
        govs = govs.filter(ngsign_status__in=STATUS_TABS[active_tab])

    # Prefetch notification states for current user
    user_states = {
        ns.gov_invoice_id: ns
        for ns in NotificationState.objects.filter(
            user=request.user,
            gov_invoice__in=govs,
        )
    }

    items = []
    for gi in govs:
        state = user_states.get(gi.id)

        # Determine read/dismissed, handle reappearance
        is_read = False
        is_dismissed = False
        if state:
            if state.status_snapshot == gi.ngsign_status:
                is_read = state.is_read
                is_dismissed = state.is_dismissed
            else:
                # Status changed — reset stale state
                state.is_read = False
                state.is_dismissed = False
                state.dismissed_at = None
                state.status_snapshot = gi.ngsign_status
                state.save(update_fields=['is_read', 'is_dismissed', 'dismissed_at', 'status_snapshot'])

        if gi.invoice:
            doc_type = 'Facture'
            doc_number = gi.invoice.uniqueId
            client_name = gi.invoice.client.clientname if gi.invoice.client else ''
            detail_url = reverse('invoice_detail', args=[gi.invoice.id])
        elif gi.credit_note:
            doc_type = 'Avoir'
            doc_number = gi.credit_note.uniqueId
            client_name = gi.credit_note.client.clientname if gi.credit_note.client else ''
            detail_url = reverse('avoir_detail', args=[gi.credit_note.id])
        else:
            continue

        items.append({
            'id': gi.id,
            'doc_type': doc_type,
            'doc_number': doc_number,
            'client_name': client_name,
            'status': gi.ngsign_status,
            'notes': gi.notes or '',
            'date': gi.created_at,
            'detail_url': detail_url,
            'is_read': is_read,
            'is_dismissed': is_dismissed,
        })

    paginator = Paginator(items, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Tab counts
    all_govs = (
        GovInvoice.objects
        .exclude(ngsign_status__isnull=True)
        .exclude(ngsign_status='')
    )
    tab_counts = {
        'all': all_govs.count(),
        'to_sign': all_govs.filter(ngsign_status__in=STATUS_TABS['to_sign']).count(),
        'errors': all_govs.filter(ngsign_status__in=STATUS_TABS['errors']).count(),
        'in_progress': all_govs.filter(ngsign_status__in=STATUS_TABS['in_progress']).count(),
        'done': all_govs.filter(ngsign_status__in=STATUS_TABS['done']).count(),
    }

    return render(request, 'sales/notifications.html', {
        'page_obj': page_obj,
        'active_tab': active_tab,
        'tab_counts': tab_counts,
    })


@login_required
def setup_wizard(request):
    """Multi-step setup wizard for first-time company configuration."""
    import base64 as _b64
    from sales.middleware import _settings_complete

    STEP_FIELDS = {
        1: ['clientname', 'status', 'emailAddress', 'phone', 'adress'],
        2: ['mf', 'tva', 'dt', 'default_retenu_rate'],
        3: ['rib', 'logo_upload'],
    }
    STEP_REQUIRED = {
        1: ['clientname', 'emailAddress', 'adress'],
        2: ['mf'],
        3: [],
    }

    step = request.session.get('setup_step', 1)
    if step not in STEP_FIELDS:
        step = 1

    if _settings_complete() and 'setup_step' not in request.session:
        return redirect('dashboard')

    settings_obj = Settings.get_cached()

    if request.method == 'POST':
        action = request.POST.get('action', 'next')

        if action == 'skip' and step == 3:
            request.session.pop('setup_step', None)
            return redirect('dashboard')

        if step == 3:
            form = SettingsForm(request.POST, request.FILES, instance=settings_obj)
        else:
            form = SettingsForm(request.POST, instance=settings_obj)

        for fname in list(form.fields.keys()):
            if fname not in STEP_FIELDS[step]:
                del form.fields[fname]
        for fname in form.fields:
            form.fields[fname].required = fname in STEP_REQUIRED[step]

        if form.is_valid():
            obj = form.save(commit=False)

            if step == 3:
                logo_file = request.FILES.get('logo_upload')
                if logo_file:
                    if logo_file.size > 2 * 1024 * 1024:
                        form.add_error('logo_upload', 'Le logo ne doit pas dépasser 2 Mo.')
                        return render(request, 'sales/setup_wizard.html', {'form': form, 'step': step})
                    raw = logo_file.read()
                    encoded = _b64.b64encode(raw).decode('utf-8')
                    obj.clientLogo = f'data:{logo_file.content_type};base64,{encoded}'
                elif settings_obj:
                    obj.clientLogo = settings_obj.clientLogo

            obj.save()

            if step == 3:
                request.session.pop('setup_step', None)
                return redirect('dashboard')
            request.session['setup_step'] = step + 1
            return redirect('setup_wizard')

    else:
        form = SettingsForm(instance=settings_obj)
        for fname in list(form.fields.keys()):
            if fname not in STEP_FIELDS[step]:
                del form.fields[fname]
        for fname in form.fields:
            form.fields[fname].required = fname in STEP_REQUIRED[step]

    return render(request, 'sales/setup_wizard.html', {'form': form, 'step': step})
