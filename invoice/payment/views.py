from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required  # Add this
from .models import InvoiceRetenu, Retenu
from sales.models import Invoice, ClientTransaction
from .forms import InvoiceRetenuForm, MultipleInvoiceRetenuForm
from decimal import Decimal

def invoice_retenu_create(request, invoice_id):
    """
    View to create a single retenue for an invoice
    """
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.method == 'POST':
        form = InvoiceRetenuForm(request.POST, invoice=invoice)
        if form.is_valid():
            retenu = form.save()
            messages.success(
                request, 
                f'Retenue ajoutée avec succès: {retenu.retenu_amount}D'
            )
            return redirect('invoice_detail', invoice_id=invoice.id)
    else:
        form = InvoiceRetenuForm(invoice=invoice)
    
    context = {
        'form': form,
        'invoice': invoice,
    }
    
    return render(request, 'invoices/retenu_create.html', context)


def invoice_retenu_add_multiple(request, invoice_id):
    """
    View to add multiple retenues at once to an invoice
    """
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.method == 'POST':
        form = MultipleInvoiceRetenuForm(request.POST, invoice=invoice)
        if form.is_valid():
            created_retenues = form.save()
            if created_retenues:
                messages.success(
                    request,
                    f'{len(created_retenues)} retenue(s) ajoutée(s) avec succès'
                )
            else:
                messages.warning(request, 'Aucune retenue sélectionnée')
            return redirect('invoice_detail', invoice_id=invoice.id)
    else:
        form = MultipleInvoiceRetenuForm(invoice=invoice)
    
    # Group retenues by category for better display
    retenu_types = Retenu.objects.filter(is_active=True).order_by('category', 'rate')
    retenu_by_category = {}
    for retenu in retenu_types:
        category = retenu.get_category_display()
        if category not in retenu_by_category:
            retenu_by_category[category] = []
        retenu_by_category[category].append(retenu)
    
    context = {
        'form': form,
        'invoice': invoice,
        'retenu_by_category': retenu_by_category,
    }
    
    return render(request, 'invoices/retenu_add_multiple.html', context)


@require_POST
def invoice_retenu_delete(request, retenu_id):
    """
    Delete a retenue from an invoice
    """
    retenu = get_object_or_404(InvoiceRetenu, id=retenu_id)
    invoice_id = retenu.invoice.id
    
    retenu.delete()
    messages.success(request, 'Retenue supprimée avec succès')
    
    return redirect('invoice_detail', invoice_id=invoice_id)


def get_retenu_rate(request, retenu_id):
    """
    AJAX endpoint to get retenu rate for calculation
    Returns JSON with rate and category info
    """
    try:
        retenu = Retenu.objects.get(id=retenu_id, is_active=True)
        return JsonResponse({
            'success': True,
            'rate': float(retenu.rate),
            'category': retenu.get_category_display(),
            'subcategory': retenu.get_subcategory_display(),
        })
    except Retenu.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Retenu type not found'
        }, status=404)


def calculate_retenu_preview(request):
    """
    AJAX endpoint to preview retenu calculation without saving
    """
    if request.method == 'GET':
        retenu_id = request.GET.get('retenu_id')
        base_amount = request.GET.get('base_amount')
        
        if not retenu_id or not base_amount:
            return JsonResponse({
                'success': False,
                'error': 'Missing parameters'
            }, status=400)
        
        try:
            from decimal import Decimal
            retenu = Retenu.objects.get(id=retenu_id, is_active=True)
            base = Decimal(base_amount)
            calculated_amount = (base * retenu.rate) / Decimal('100')
            
            return JsonResponse({
                'success': True,
                'rate': float(retenu.rate),
                'base_amount': float(base),
                'calculated_amount': float(calculated_amount),
                'retenu_type': str(retenu),
            })
        except (Retenu.DoesNotExist, ValueError, Exception) as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)


def payment_detail(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # Get all retenues for this invoice
    retenues = invoice.retenues.all()
    
    # Calculate totals
    total_retenue = invoice.get_total_retenue()
    net_amount = invoice.get_net_amount()
    
    context = {
        'invoice': invoice,
        'retenues': retenues,
        'total_retenue': total_retenue,
        'net_amount': net_amount,
        'has_retenue': invoice.has_retenue(),
    }
    
    return render(request, 'invoices/invoice_detail.html', context)


@login_required
@require_POST
def process_payment(request, invoice_id):
    """Process full or partial payment for an invoice."""
    invoice = get_object_or_404(Invoice.objects.prefetch_related('invoice_services'), id=invoice_id)

    try:
        payment_amount = Decimal(request.POST.get('payment_amount', '0'))
    except Exception:
        payment_amount = Decimal('0')

    payment_notes = request.POST.get('payment_notes', '')

    total = invoice.calculate_total()
    credit_notes_total = sum(cn.calculate_total() for cn in invoice.credit_notes.all())
    effective_total = total - credit_notes_total
    remaining = effective_total - invoice.amount_paid

    # Clamp to what's still owed
    payment_amount = min(payment_amount, remaining)

    if payment_amount <= 0:
        messages.error(request, 'Montant invalide ou facture déjà soldée.')
        return redirect('invoices_list')

    invoice.amount_paid += payment_amount
    if invoice.amount_paid >= effective_total:
        invoice.status = 'PAID'
    invoice.save()

    if invoice.client:
        ClientTransaction.objects.create(
            client=invoice.client,
            invoice=invoice,
            transaction_type='CREDIT',
            source='INVOICE_PAID',
            amount=payment_amount,
            description=f'Paiement facture {invoice.uniqueId} — {payment_amount:.3f} D'
            + (f' — {payment_notes}' if payment_notes else ''),
        )

    messages.success(
        request,
        f'Paiement de {payment_amount:.3f} D enregistré pour la facture #{invoice.uniqueId or invoice.id}.'
        + (' Facture soldée.' if invoice.status == 'PAID' else f' Reste : {(effective_total - invoice.amount_paid):.3f} D.')
    )

    return redirect('invoice_detail', invoice_id=invoice.id)