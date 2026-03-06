# Devis (Quote) Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Devis (quote/estimate) document type that can be converted into a real Invoice with one click.

**Architecture:** A separate `Devis` model lives in `sales/models.py`. Instead of a separate `DevisService` model, the existing `InvoiceService` model is extended with an optional `devis` FK — so one line item row belongs to either an invoice OR a devis. `convert_to_invoice()` creates the `Invoice` and **copies** the `InvoiceService` rows to the invoice, leaving the devis rows intact as a frozen historical record.

**Tech Stack:** Django 6, PostgreSQL (django-tenants), Bootstrap 5, existing `sales` app patterns.

---

## Task 1: Extend `InvoiceService` + add `Devis` model

**Files:**
- Modify: `invoice/sales/models.py`

### Step 1: Make `InvoiceService.invoice` nullable and add `devis` FK

Find the `InvoiceService` class (~line 790) and change the `invoice` field + add `devis`:

```python
class InvoiceService(models.Model):
    invoice = models.ForeignKey(
        'Invoice', null=True, blank=True,
        on_delete=models.CASCADE, related_name='invoice_services'
    )
    devis = models.ForeignKey(
        'Devis', null=True, blank=True,
        on_delete=models.CASCADE, related_name='devis_services'
    )
    service = models.ForeignKey('Service', on_delete=models.PROTECT)

    hours_used = models.PositiveIntegerField(null=True, blank=True)
    days_used = models.PositiveIntegerField(null=True, blank=True)
    units_used = models.PositiveIntegerField(null=True, blank=True)
    unit_price = models.DecimalField(max_digits=15, decimal_places=3)
    has_fodec = models.BooleanField(default=False)

    # ... all existing methods unchanged (get_line_ht, get_fodec_amount, get_vat_base)
```

> **Note:** The `invoice` FK already exists — only change is `null=True, blank=True`. Add the new `devis` FK below it. All existing `get_line_ht`, `get_fodec_amount`, `get_vat_base` methods stay identical.

### Step 2: Add the `Devis` model

Append to the end of `invoice/sales/models.py`:

```python
class Devis(models.Model):
    STATUS = [
        ('PENDING', 'PENDING'),
        ('ACCEPTED', 'ACCEPTED'),
        ('REJECTED', 'REJECTED'),
    ]

    client = models.ForeignKey('Client', blank=True, null=True, on_delete=models.SET_NULL)
    title = models.CharField(null=True, blank=True, max_length=200)
    notes = models.TextField(null=True, blank=True)
    status = models.CharField(choices=STATUS, default='PENDING', max_length=100)

    tva = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)

    converted_invoice = models.OneToOneField(
        'Invoice', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='source_devis'
    )

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, null=True, blank=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']
        verbose_name_plural = 'Devis'

    def __str__(self):
        return f"Devis {self.uniqueId} - {self.client}"

    def get_tva(self):
        if self.tva is not None:
            return Decimal(str(self.tva))
        return Decimal('19.00')

    def get_timbre_fiscal(self):
        if self.timbre_fiscal is not None:
            return Decimal(str(self.timbre_fiscal))
        return Decimal('1.000')

    def calculate_service_subtotal(self):
        return sum(s.get_line_ht() for s in self.devis_services.all())

    def calculate_total_fodec(self):
        return sum(s.get_fodec_amount() for s in self.devis_services.all())

    def calculate_discount_amount(self):
        subtotal = self.calculate_service_subtotal()
        fodec = self.calculate_total_fodec()
        if self.discount:
            return (subtotal + fodec) * Decimal(str(self.discount)) / Decimal('100')
        return Decimal('0')

    def calculate_tva_amount(self):
        subtotal = self.calculate_service_subtotal()
        fodec = self.calculate_total_fodec()
        discount = self.calculate_discount_amount()
        tva_base = subtotal + fodec - discount
        return tva_base * self.get_tva() / Decimal('100')

    def calculate_total(self):
        subtotal = self.calculate_service_subtotal()
        fodec = self.calculate_total_fodec()
        discount = self.calculate_discount_amount()
        tva = self.calculate_tva_amount()
        timbre = self.get_timbre_fiscal()
        return subtotal + fodec - discount + tva + timbre

    def convert_to_invoice(self):
        """
        Creates an Invoice from this devis.
        Copies each InvoiceService row to the new invoice — the devis keeps
        its own rows as a frozen historical record.
        Marks self as ACCEPTED and stores the link.
        """
        if self.converted_invoice:
            return self.converted_invoice

        invoice = Invoice.objects.create(
            client=self.client,
            title=self.title or '',
            notes=self.notes or '',
            tva=self.tva,
            timbre_fiscal=self.timbre_fiscal,
            discount=self.discount or 0,
        )

        # Copy line items — devis keeps its rows, invoice gets new independent rows
        for ds in self.devis_services.all():
            InvoiceService.objects.create(
                invoice=invoice,
                service=ds.service,
                hours_used=ds.hours_used,
                days_used=ds.days_used,
                units_used=ds.units_used,
                unit_price=ds.unit_price,
                has_fodec=ds.has_fodec,
            )

        self.converted_invoice = invoice
        self.status = 'ACCEPTED'
        self.save()
        return invoice

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
            settings = Settings.get_cached()
            if settings:
                if self.tva is None and settings.tva is not None:
                    self.tva = Decimal(str(settings.tva))
                if self.timbre_fiscal is None and settings.dt is not None:
                    self.timbre_fiscal = Decimal(str(settings.dt))

        if not self.uniqueId:
            year = str(now.year)
            existing = Devis.objects.filter(
                uniqueId__startswith='DV-',
                uniqueId__endswith=f'-{year}'
            ).order_by('-date_created')
            if existing.exists():
                last_id = existing.first().uniqueId
                try:
                    last_number = int(last_id.split('-')[1])
                except (ValueError, IndexError):
                    last_number = 0
                next_number = last_number + 1
            else:
                next_number = 1
            self.uniqueId = f"DV-{str(next_number).zfill(3)}-{year}"

        if not self.slug:
            base_slug = slugify(self.title or "devis")
            self.slug = f"{base_slug}-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)
```

### Step 3: Create and run migrations

```bash
cd invoice
python manage.py makemigrations sales --name devis_invoiceservice_shared
```

Expected output: new migration that makes `InvoiceService.invoice` nullable, adds `InvoiceService.devis` FK, and creates the `Devis` table.

```bash
python manage.py migrate   # local sqlite / or migrate_schemas on postgres
```

### Step 4: Commit

```bash
git add invoice/sales/models.py invoice/sales/migrations/
git commit -m "feat: add Devis model, extend InvoiceService for shared line items"
```

---

## Task 2: Add views

**Files:**
- Modify: `invoice/sales/views.py` (append 6 new views at the end)

**Step 1: Ensure `Devis` is imported**

At the top of `invoice/sales/views.py`, `Devis` is in `sales.models`. The existing import block already imports from `.models` — add `Devis` to it:
```python
from .models import (
    ...,  # existing
    Devis,
)
```

**Step 2: Append the 6 views**

```python
# ─────────────────────────────────────────────
# DEVIS (Quotes / Approximation Invoices)
# ─────────────────────────────────────────────

@login_required
def devis_list(request):
    devis_qs = Devis.objects.select_related('client', 'converted_invoice').all()
    return render(request, 'sales/devis_list.html', {
        'devis_list': devis_qs,
        'count': devis_qs.count(),
        'accepted_count': devis_qs.filter(status='ACCEPTED').count(),
        'pending_count': devis_qs.filter(status='PENDING').count(),
        'rejected_count': devis_qs.filter(status='REJECTED').count(),
        'clients': Client.objects.all(),
        'services': Service.objects.all(),
        'settings': Settings.get_cached(),
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
    return render(request, 'sales/devis_detail.html', {
        'devis': devis,
        'settings': Settings.get_cached(),
        'clients': Client.objects.all(),
        'services': Service.objects.all(),
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
```

**Step 3: Commit**

```bash
git add invoice/sales/views.py
git commit -m "feat: add devis views"
```

---

## Task 3: Add URLs

**Files:**
- Modify: `invoice/sales/urls.py`

**Step 1: Add to the import block at top**

In the `from .views import (...)` block, add:
```python
devis_list, devis_create, devis_detail, devis_update, devis_delete, devis_convert,
```

**Step 2: Add URL patterns before the closing `]`**

```python
    # Devis (Quotes)
    path('devis/', devis_list, name='devis_list'),
    path('devis/create/', devis_create, name='devis_create'),
    path('devis/<int:devis_id>/', devis_detail, name='devis_detail'),
    path('devis/<int:devis_id>/update/', devis_update, name='devis_update'),
    path('devis/<int:devis_id>/delete/', devis_delete, name='devis_delete'),
    path('devis/<int:devis_id>/convert/', devis_convert, name='devis_convert'),
```

**Step 3: Commit**

```bash
git add invoice/sales/urls.py
git commit -m "feat: add devis URL patterns"
```

---

## Task 4: Create templates

**Files:**
- Create: `invoice/templates/sales/devis_list.html`
- Create: `invoice/templates/sales/devis_detail.html`
- Create: `invoice/templates/sales/devis_delete.html`

> All templates extend `partials/base.html` and use Bootstrap 5 + `bi` icons, matching the style of `avoirs.html` and `invoice_detail_service.html`.

### 4a — `devis_list.html`

```html
{% extends 'partials/base.html' %}
{% load static %}
{% block title %}Devis{% endblock %}
{% block main %}

<div class="page-header d-flex justify-content-between align-items-center">
  <div>
    <h1>Devis</h1>
    <p>Gérer vos devis et estimations</p>
  </div>
  <div class="page-header-actions">
    <button type="button" class="btn btn-modern-primary btn-modern"
            data-bs-toggle="modal" data-bs-target="#createDevisModal">
      <i class="bi bi-plus-circle me-2"></i>Créer un devis
    </button>
  </div>
</div>

<div class="row g-3 mb-4">
  <div class="col-md-3">
    <div class="modern-card text-center py-3">
      <div class="fs-4 fw-bold text-primary">{{ count }}</div>
      <div class="text-muted small">Total</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="modern-card text-center py-3">
      <div class="fs-4 fw-bold text-warning">{{ pending_count }}</div>
      <div class="text-muted small">En attente</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="modern-card text-center py-3">
      <div class="fs-4 fw-bold text-success">{{ accepted_count }}</div>
      <div class="text-muted small">Acceptés</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="modern-card text-center py-3">
      <div class="fs-4 fw-bold text-danger">{{ rejected_count }}</div>
      <div class="text-muted small">Rejetés</div>
    </div>
  </div>
</div>

<div class="modern-card">
  <div class="table-responsive">
    <table class="table table-hover align-middle mb-0">
      <thead>
        <tr>
          <th>Numéro</th>
          <th>Client</th>
          <th>Statut</th>
          <th>Date</th>
          <th>Facture liée</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {% for d in devis_list %}
        <tr>
          <td><strong>{{ d.uniqueId }}</strong></td>
          <td>{{ d.client.clientname|default:"—" }}</td>
          <td>
            {% if d.status == 'ACCEPTED' %}<span class="badge bg-success">Accepté</span>
            {% elif d.status == 'REJECTED' %}<span class="badge bg-danger">Rejeté</span>
            {% else %}<span class="badge bg-warning text-dark">En attente</span>{% endif %}
          </td>
          <td>{{ d.date_created|date:"d/m/Y" }}</td>
          <td>
            {% if d.converted_invoice %}
              <a href="{% url 'invoice_detail' d.converted_invoice.id %}">{{ d.converted_invoice.uniqueId }}</a>
            {% else %}—{% endif %}
          </td>
          <td class="text-end">
            <a href="{% url 'devis_detail' d.id %}" class="btn btn-sm btn-outline-primary"><i class="bi bi-eye"></i></a>
            <a href="{% url 'devis_delete' d.id %}" class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></a>
          </td>
        </tr>
        {% empty %}
        <tr><td colspan="6" class="text-center text-muted py-4">Aucun devis trouvé.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<!-- Create Modal -->
<div class="modal fade" id="createDevisModal" tabindex="-1">
  <div class="modal-dialog modal-lg modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Créer un devis</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <form method="POST" action="{% url 'devis_create' %}">
        {% csrf_token %}
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label">Client *</label>
            <select name="client" class="form-select" required>
              <option value="">— Sélectionner —</option>
              {% for c in clients %}<option value="{{ c.id }}">{{ c.clientname }}</option>{% endfor %}
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Titre</label>
            <input type="text" name="title" class="form-control">
          </div>
          <div class="row g-3 mb-3">
            <div class="col-md-4">
              <label class="form-label">TVA (%)</label>
              <input type="number" name="tva" class="form-control" step="0.01" value="{{ settings.tva|default:'19.00' }}">
            </div>
            <div class="col-md-4">
              <label class="form-label">Timbre fiscal</label>
              <input type="number" name="timbre_fiscal" class="form-control" step="0.001" value="{{ settings.dt|default:'1.000' }}">
            </div>
            <div class="col-md-4">
              <label class="form-label">Remise (%)</label>
              <input type="number" name="discount" class="form-control" step="0.01" value="0">
            </div>
          </div>
          <div class="mb-3">
            <label class="form-label">Notes</label>
            <textarea name="notes" class="form-control" rows="2"></textarea>
          </div>
          <hr>
          <div class="d-flex justify-content-between align-items-center mb-2">
            <strong>Services</strong>
            <button type="button" class="btn btn-sm btn-outline-primary" id="addDevisServiceBtn">
              <i class="bi bi-plus"></i> Ajouter
            </button>
          </div>
          <div id="devisServiceRows"></div>
          <template id="devisServiceRowTpl">
            <div class="devis-service-row border rounded p-2 mb-2">
              <div class="row g-2 align-items-end">
                <div class="col-md-4">
                  <label class="form-label small">Service</label>
                  <select name="service_id[]" class="form-select form-select-sm svc-select" required>
                    <option value="">— Choisir —</option>
                    {% for s in services %}
                    <option value="{{ s.id }}" data-price="{{ s.price }}" data-billing="{{ s.billing_type }}" data-fodec="{{ s.apply_fodec|yesno:'1,0' }}">{{ s.title }}</option>
                    {% endfor %}
                  </select>
                </div>
                <div class="col-md-2">
                  <label class="form-label small">Prix unit.</label>
                  <input type="number" name="unit_price[]" class="form-control form-control-sm" step="0.001" required>
                </div>
                <div class="col-md-2">
                  <label class="form-label small">Qté/Hrs/Jrs</label>
                  <input type="number" name="hours_used[]" class="form-control form-control-sm hours-f" min="1">
                  <input type="number" name="days_used[]"  class="form-control form-control-sm days-f d-none" min="1">
                  <input type="number" name="units_used[]" class="form-control form-control-sm units-f d-none" min="1">
                </div>
                <div class="col-md-2">
                  <div class="form-check mt-3">
                    <input type="checkbox" name="has_fodec[]" value="1" class="form-check-input">
                    <label class="form-check-label small">FODEC</label>
                  </div>
                </div>
                <div class="col-md-2">
                  <button type="button" class="btn btn-sm btn-outline-danger remove-row-btn"><i class="bi bi-x"></i></button>
                </div>
              </div>
            </div>
          </template>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
          <button type="submit" class="btn btn-primary">Créer le devis</button>
        </div>
      </form>
    </div>
  </div>
</div>

<script>
function wireRow(row) {
  row.querySelector('.remove-row-btn').onclick = () => row.remove();
  row.querySelector('.svc-select').onchange = function() {
    const opt = this.options[this.selectedIndex];
    row.querySelector('[name="unit_price[]"]').value = opt.dataset.price || '';
    const b = opt.dataset.billing;
    row.querySelector('.hours-f').classList.toggle('d-none', b !== 'hour');
    row.querySelector('.days-f').classList.toggle('d-none', b !== 'day');
    row.querySelector('.units-f').classList.toggle('d-none', b !== 'unit');
    if (opt.dataset.fodec === '1') row.querySelector('[name="has_fodec[]"]').checked = true;
  };
}
document.getElementById('addDevisServiceBtn').addEventListener('click', function() {
  const clone = document.getElementById('devisServiceRowTpl').content.cloneNode(true);
  const row = clone.querySelector('.devis-service-row');
  document.getElementById('devisServiceRows').appendChild(clone);
  wireRow(document.getElementById('devisServiceRows').lastElementChild);
});
</script>
{% endblock %}
```

### 4b — `devis_detail.html`

```html
{% extends 'partials/base.html' %}
{% load static %}
{% block title %}Devis #{{ devis.uniqueId }}{% endblock %}
{% block main %}

<div style="max-width:900px;margin:0 auto;">
  <!-- Action bar -->
  <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
    <a href="{% url 'devis_list' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-arrow-left me-1"></i>Retour
    </a>
    <div class="d-flex gap-2 flex-wrap">
      {% if devis.status == 'PENDING' %}
        <button data-bs-toggle="modal" data-bs-target="#editDevisModal" class="btn btn-sm btn-outline-primary">
          <i class="bi bi-pencil me-1"></i>Modifier
        </button>
        <form method="POST" action="{% url 'devis_convert' devis.id %}" class="d-inline"
              onsubmit="return confirm('Convertir ce devis en facture ?')">
          {% csrf_token %}
          <button type="submit" class="btn btn-sm btn-success">
            <i class="bi bi-arrow-right-circle me-1"></i>Convertir en facture
          </button>
        </form>
        <form method="POST" action="{% url 'devis_update' devis.id %}" class="d-inline">
          {% csrf_token %}
          <input type="hidden" name="status" value="REJECTED">
          <button type="submit" class="btn btn-sm btn-outline-danger"
                  onclick="return confirm('Marquer comme rejeté ?')">
            <i class="bi bi-x-circle me-1"></i>Rejeter
          </button>
        </form>
      {% elif devis.status == 'ACCEPTED' %}
        <a href="{% url 'invoice_detail' devis.converted_invoice.id %}" class="btn btn-sm btn-success">
          <i class="bi bi-file-earmark-check me-1"></i>Voir facture {{ devis.converted_invoice.uniqueId }}
        </a>
      {% elif devis.status == 'REJECTED' %}
        <button data-bs-toggle="modal" data-bs-target="#editDevisModal" class="btn btn-sm btn-outline-secondary">
          <i class="bi bi-pencil me-1"></i>Modifier
        </button>
      {% endif %}
      <button onclick="window.print()" class="btn btn-sm btn-outline-secondary">
        <i class="bi bi-printer me-1"></i>Imprimer
      </button>
      <a href="{% url 'devis_delete' devis.id %}" class="btn btn-sm btn-outline-danger">
        <i class="bi bi-trash me-1"></i>Supprimer
      </a>
    </div>
  </div>

  <!-- Document -->
  <div class="bg-white rounded shadow-sm overflow-hidden">
    <div class="p-4 border-bottom" style="background:#eff6ff;">
      <div class="d-flex justify-content-between align-items-start">
        <div>
          {% if settings.clientLogo %}<img src="{{ settings.clientLogo }}" alt="Logo" style="max-height:60px;" class="mb-2">{% endif %}
          <div class="fw-bold">{{ settings.clientname|default:"" }}</div>
          <div class="text-muted small">{{ settings.address|default:"" }}</div>
          <div class="text-muted small">MF: {{ settings.mf|default:"" }}</div>
        </div>
        <div class="text-end">
          <h2 class="text-primary fw-bold mb-1">DEVIS</h2>
          <div class="fs-5 fw-semibold">#{{ devis.uniqueId }}</div>
          <div class="text-muted small">{{ devis.date_created|date:"d/m/Y" }}</div>
          <div class="mt-1">
            {% if devis.status == 'ACCEPTED' %}<span class="badge bg-success">Accepté</span>
            {% elif devis.status == 'REJECTED' %}<span class="badge bg-danger">Rejeté</span>
            {% else %}<span class="badge bg-warning text-dark">En attente</span>{% endif %}
          </div>
        </div>
      </div>
    </div>

    <div class="p-4 border-bottom">
      <div class="text-muted small text-uppercase mb-1">Client</div>
      <div class="fw-bold">{{ devis.client.clientname|default:"—" }}</div>
      <div class="text-muted small">{{ devis.client.address|default:"" }}</div>
      <div class="text-muted small">MF: {{ devis.client.mf|default:"" }}</div>
    </div>

    <div class="p-4">
      <table class="table table-sm">
        <thead class="table-light">
          <tr>
            <th>Service</th><th class="text-end">Prix unit.</th><th class="text-end">Qté</th>
            <th class="text-end">FODEC</th><th class="text-end">Montant HT</th>
          </tr>
        </thead>
        <tbody>
          {% for ds in devis.devis_services.all %}
          <tr>
            <td>{{ ds.service.title }}</td>
            <td class="text-end">{{ ds.unit_price }}</td>
            <td class="text-end">
              {% if ds.service.billing_type == 'hour' %}{{ ds.hours_used|default:1 }} h
              {% elif ds.service.billing_type == 'day' %}{{ ds.days_used|default:1 }} j
              {% elif ds.service.billing_type == 'unit' %}{{ ds.units_used|default:1 }}
              {% else %}—{% endif %}
            </td>
            <td class="text-end">{% if ds.has_fodec %}✓{% else %}—{% endif %}</td>
            <td class="text-end">{{ ds.get_line_ht }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>

      <div class="row justify-content-end mt-3">
        <div class="col-md-5">
          <table class="table table-sm table-borderless">
            <tr><td>Sous-total HT</td><td class="text-end">{{ devis.calculate_service_subtotal }}</td></tr>
            {% if devis.calculate_total_fodec %}<tr><td>FODEC (1%)</td><td class="text-end">{{ devis.calculate_total_fodec }}</td></tr>{% endif %}
            {% if devis.discount %}<tr><td>Remise ({{ devis.discount }}%)</td><td class="text-end">-{{ devis.calculate_discount_amount }}</td></tr>{% endif %}
            <tr><td>TVA ({{ devis.get_tva }}%)</td><td class="text-end">{{ devis.calculate_tva_amount }}</td></tr>
            <tr><td>Timbre fiscal</td><td class="text-end">{{ devis.get_timbre_fiscal }}</td></tr>
            <tr class="fw-bold border-top"><td>TOTAL TTC</td><td class="text-end">{{ devis.calculate_total }} TND</td></tr>
          </table>
        </div>
      </div>

      {% if devis.notes %}
      <div class="mt-3 p-3 bg-light rounded">
        <div class="text-muted small text-uppercase mb-1">Notes</div>
        <div>{{ devis.notes }}</div>
      </div>
      {% endif %}
    </div>
  </div>
</div>

<!-- Edit Modal -->
<div class="modal fade" id="editDevisModal" tabindex="-1">
  <div class="modal-dialog modal-lg modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Modifier {{ devis.uniqueId }}</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <form method="POST" action="{% url 'devis_update' devis.id %}">
        {% csrf_token %}
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label">Client</label>
            <select name="client" class="form-select">
              {% for c in clients %}
              <option value="{{ c.id }}" {% if c.id == devis.client_id %}selected{% endif %}>{{ c.clientname }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Titre</label>
            <input type="text" name="title" class="form-control" value="{{ devis.title|default:'' }}">
          </div>
          <div class="row g-3 mb-3">
            <div class="col-md-4">
              <label class="form-label">TVA (%)</label>
              <input type="number" name="tva" class="form-control" step="0.01" value="{{ devis.tva }}">
            </div>
            <div class="col-md-4">
              <label class="form-label">Timbre fiscal</label>
              <input type="number" name="timbre_fiscal" class="form-control" step="0.001" value="{{ devis.timbre_fiscal }}">
            </div>
            <div class="col-md-4">
              <label class="form-label">Remise (%)</label>
              <input type="number" name="discount" class="form-control" step="0.01" value="{{ devis.discount|default:'0' }}">
            </div>
          </div>
          <div class="mb-3">
            <label class="form-label">Notes</label>
            <textarea name="notes" class="form-control" rows="2">{{ devis.notes|default:'' }}</textarea>
          </div>
          <hr>
          <div class="d-flex justify-content-between align-items-center mb-2">
            <strong>Services</strong>
            <button type="button" class="btn btn-sm btn-outline-primary" id="addEditSvcBtn">
              <i class="bi bi-plus"></i> Ajouter
            </button>
          </div>
          <div id="editSvcRows">
            {% for ds in devis.devis_services.all %}
            <div class="devis-service-row border rounded p-2 mb-2">
              <div class="row g-2 align-items-end">
                <div class="col-md-4">
                  <select name="service_id[]" class="form-select form-select-sm" required>
                    {% for s in services %}
                    <option value="{{ s.id }}" data-price="{{ s.price }}" data-billing="{{ s.billing_type }}"
                            {% if s.id == ds.service_id %}selected{% endif %}>{{ s.title }}</option>
                    {% endfor %}
                  </select>
                </div>
                <div class="col-md-2">
                  <input type="number" name="unit_price[]" class="form-control form-control-sm" step="0.001" value="{{ ds.unit_price }}" required>
                </div>
                <div class="col-md-2">
                  <input type="number" name="hours_used[]" class="form-control form-control-sm {% if ds.service.billing_type != 'hour' %}d-none{% endif %}" value="{{ ds.hours_used|default:'' }}" min="1">
                  <input type="number" name="days_used[]"  class="form-control form-control-sm {% if ds.service.billing_type != 'day'  %}d-none{% endif %}" value="{{ ds.days_used|default:'' }}"  min="1">
                  <input type="number" name="units_used[]" class="form-control form-control-sm {% if ds.service.billing_type != 'unit' %}d-none{% endif %}" value="{{ ds.units_used|default:'' }}" min="1">
                </div>
                <div class="col-md-2">
                  <div class="form-check mt-3">
                    <input type="checkbox" name="has_fodec[]" value="1" class="form-check-input" {% if ds.has_fodec %}checked{% endif %}>
                    <label class="form-check-label small">FODEC</label>
                  </div>
                </div>
                <div class="col-md-2">
                  <button type="button" class="btn btn-sm btn-outline-danger remove-row-btn"><i class="bi bi-x"></i></button>
                </div>
              </div>
            </div>
            {% endfor %}
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
          <button type="submit" class="btn btn-primary">Enregistrer</button>
        </div>
      </form>
    </div>
  </div>
</div>
<script>
document.querySelectorAll('.remove-row-btn').forEach(b => b.onclick = () => b.closest('.devis-service-row').remove());
document.getElementById('addEditSvcBtn').addEventListener('click', function() {
  const tpl = document.getElementById('devisServiceRowTpl');
  if (!tpl) return;
  const clone = tpl.content.cloneNode(true);
  document.getElementById('editSvcRows').appendChild(clone);
  const row = document.getElementById('editSvcRows').lastElementChild;
  row.querySelector('.remove-row-btn').onclick = () => row.remove();
});
</script>
{% endblock %}
```

### 4c — `devis_delete.html`

```html
{% extends 'partials/base.html' %}
{% block title %}Supprimer Devis{% endblock %}
{% block main %}
<div class="modern-card" style="max-width:500px;margin:2rem auto;">
  <h4>Supprimer le devis {{ devis.uniqueId }} ?</h4>
  <p class="text-muted">Cette action est irréversible.</p>
  <form method="POST">
    {% csrf_token %}
    <a href="{% url 'devis_detail' devis.id %}" class="btn btn-secondary me-2">Annuler</a>
    <button type="submit" class="btn btn-danger">Supprimer</button>
  </form>
</div>
{% endblock %}
```

**Commit after all 3 templates:**

```bash
git add invoice/templates/sales/devis_list.html \
        invoice/templates/sales/devis_detail.html \
        invoice/templates/sales/devis_delete.html
git commit -m "feat: add devis templates"
```

---

## Task 5: Add nav link

**Files:**
- Modify: `invoice/templates/partials/base.html`

Find the nav section with links like Avoirs, Bons de Livraison. Add after the Avoirs link:

```html
<li class="nav-item">
  <a class="nav-link {% if request.resolver_match.url_name|slice:':5' == 'devis' %}active{% endif %}"
     href="{% url 'devis_list' %}">
    <i class="bi bi-file-earmark-text me-2"></i>Devis
  </a>
</li>
```

**Commit:**

```bash
git add invoice/templates/partials/base.html
git commit -m "feat: add Devis nav link"
```

---

## Task 6: Deploy & smoke test

**Step 1:** Push to repo, Dokploy redeploys automatically.

**Step 2:** Check Dokploy logs for:
```
Applying sales.XXXX_devis_invoiceservice_shared... OK
```

**Step 3: Smoke test checklist**

1. `/devis/` → empty list, 4 stat cards visible
2. "Créer un devis" → fill client + add a service → submit → redirects to detail with `DV-001-YEAR`
3. Detail page → totals correct, status PENDING, action buttons visible
4. "Convertir en facture" → redirects to new `FV-###-YEAR` invoice
5. Back to `/devis/` → devis shows ACCEPTED + link to invoice
6. Linked invoice detail → line items present and correct
7. Delete a PENDING devis → confirms, removes, redirects to list
