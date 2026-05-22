# Distributor Invoice App - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add truck management, trip lifecycle, walk-in sales, and restocking to the existing Django invoice app for distributors.

**Architecture:** Hybrid truck-as-warehouse approach. Trucks have persistent inventory modified only through Trips. Walk-in sales deduct directly from warehouse (Supply.stock_quantity). Restocking via Purchase (RECEIVED) and manual StockAdjustment. All new models live in the existing `sales` app.

**Tech Stack:** Django 4.x, PostgreSQL (django-tenants), crispy-forms/bootstrap5, existing template patterns

**Design doc:** `docs/plans/2026-03-09-distributor-invoice-app-design.md`

---

## Task 1: Add `source` field to Invoice model

**Files:**
- Modify: `invoice/sales/models.py` (Invoice class, ~line 354)

**Step 1: Add the field**

Add to the Invoice model, after the `is_locked` field:

```python
SOURCE_CHOICES = [
    ('STANDARD', 'Standard'),
    ('WALK_IN', 'Walk-in Sale'),
    ('TRUCK_SALE', 'Truck Sale'),
]
source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='STANDARD')
```

**Step 2: Make migration**

Run: `python manage.py makemigrations sales`
Expected: New migration file created

**Step 3: Apply migration**

Run: `python manage.py migrate`
Expected: Migration applied successfully

**Step 4: Commit**

```bash
git add invoice/sales/models.py invoice/sales/migrations/
git commit -m "feat: add source field to Invoice model (STANDARD, WALK_IN, TRUCK_SALE)"
```

---

## Task 2: Add Truck and TruckInventory models

**Files:**
- Modify: `invoice/sales/models.py` (append after last model)
- Modify: `invoice/sales/admin.py` (register new models)

**Step 1: Add Truck model**

Append to `invoice/sales/models.py`:

```python
class Truck(models.Model):
    name = models.CharField(max_length=200)
    plate_number = models.CharField(max_length=50, blank=True, null=True)
    zone = models.CharField(max_length=200, blank=True, null=True, help_text="Area/region assigned")
    driver_name = models.CharField(max_length=200, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    uniqueId = models.CharField(max_length=100, blank=True, null=True)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.plate_number or 'No plate'})"

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
        if not self.uniqueId:
            self.uniqueId = uuid4().hex[:8]
        if not self.slug:
            self.slug = f"{slugify(self.name or 'truck')}-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)


class TruckInventory(models.Model):
    truck = models.ForeignKey('Truck', on_delete=models.CASCADE, related_name='inventory_items')
    service = models.ForeignKey('Service', on_delete=models.PROTECT, related_name='truck_inventory')
    quantity = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    class Meta:
        unique_together = ('truck', 'service')
        verbose_name_plural = "Truck Inventories"

    def __str__(self):
        return f"{self.truck.name} - {self.service.title}: {self.quantity}"
```

**Step 2: Register in admin**

Add to `invoice/sales/admin.py`:

```python
from .models import Truck, TruckInventory
admin.site.register(Truck)
admin.site.register(TruckInventory)
```

**Step 3: Make and apply migration**

Run: `python manage.py makemigrations sales && python manage.py migrate`

**Step 4: Commit**

```bash
git add invoice/sales/models.py invoice/sales/admin.py invoice/sales/migrations/
git commit -m "feat: add Truck and TruckInventory models"
```

---

## Task 3: Add Trip, TripLoadLine models

**Files:**
- Modify: `invoice/sales/models.py` (append)
- Modify: `invoice/sales/admin.py`

**Step 1: Add models**

Append to `invoice/sales/models.py`:

```python
class Trip(models.Model):
    STATUS = [
        ('LOADING', 'Loading'),
        ('IN_PROGRESS', 'In Progress'),
        ('RECONCILING', 'Reconciling'),
        ('COMPLETED', 'Completed'),
    ]

    truck = models.ForeignKey('Truck', on_delete=models.CASCADE, related_name='trips')
    status = models.CharField(max_length=20, choices=STATUS, default='LOADING')
    date_departure = models.DateTimeField(blank=True, null=True)
    date_return = models.DateTimeField(blank=True, null=True)
    zone = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    uniqueId = models.CharField(max_length=100, blank=True, null=True)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"Trip {self.uniqueId} - {self.truck.name}"

    def save(self, *args, **kwargs):
        now = timezone.localtime(timezone.now())
        if not self.date_created:
            self.date_created = now
        if not self.zone and self.truck:
            self.zone = self.truck.zone
        if not self.uniqueId:
            year = str(now.year)
            existing = Trip.objects.filter(
                uniqueId__startswith='TR-',
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
            self.uniqueId = f"TR-{str(next_number).zfill(3)}-{year}"
        if not self.slug:
            self.slug = f"trip-{self.uniqueId}"
        self.last_updated = now
        super().save(*args, **kwargs)


class TripLoadLine(models.Model):
    trip = models.ForeignKey('Trip', on_delete=models.CASCADE, related_name='load_lines')
    service = models.ForeignKey('Service', on_delete=models.PROTECT)
    quantity_loaded = models.DecimalField(max_digits=15, decimal_places=3)

    class Meta:
        unique_together = ('trip', 'service')

    def __str__(self):
        return f"{self.service.title} x {self.quantity_loaded}"
```

**Step 2: Register in admin**

```python
from .models import Trip, TripLoadLine
admin.site.register(Trip)
admin.site.register(TripLoadLine)
```

**Step 3: Make and apply migration**

Run: `python manage.py makemigrations sales && python manage.py migrate`

**Step 4: Commit**

```bash
git add invoice/sales/models.py invoice/sales/admin.py invoice/sales/migrations/
git commit -m "feat: add Trip and TripLoadLine models"
```

---

## Task 4: Add TripSale, TripSaleLine models

**Files:**
- Modify: `invoice/sales/models.py` (append)
- Modify: `invoice/sales/admin.py`

**Step 1: Add models**

Append to `invoice/sales/models.py`:

```python
class TripSale(models.Model):
    trip = models.ForeignKey('Trip', on_delete=models.CASCADE, related_name='sales')
    client = models.ForeignKey('Client', on_delete=models.SET_NULL, null=True, blank=True)
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_sale')
    is_cash_sale = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        if self.is_cash_sale:
            return f"Cash sale - Trip {self.trip.uniqueId}"
        return f"Sale to {self.client} - Trip {self.trip.uniqueId}"

    def save(self, *args, **kwargs):
        if not self.date_created:
            self.date_created = timezone.localtime(timezone.now())
        super().save(*args, **kwargs)

    def get_total(self):
        return sum(line.quantity * line.unit_price for line in self.lines.all())


class TripSaleLine(models.Model):
    trip_sale = models.ForeignKey('TripSale', on_delete=models.CASCADE, related_name='lines')
    service = models.ForeignKey('Service', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=15, decimal_places=3)
    unit_price = models.DecimalField(max_digits=15, decimal_places=3)

    def __str__(self):
        return f"{self.service.title} x {self.quantity} @ {self.unit_price}"

    def get_line_total(self):
        return self.quantity * self.unit_price
```

**Step 2: Register in admin**

```python
from .models import TripSale, TripSaleLine
admin.site.register(TripSale)
admin.site.register(TripSaleLine)
```

**Step 3: Make and apply migration, commit**

```bash
python manage.py makemigrations sales && python manage.py migrate
git add invoice/sales/models.py invoice/sales/admin.py invoice/sales/migrations/
git commit -m "feat: add TripSale and TripSaleLine models"
```

---

## Task 5: Add TripReconciliation models

**Files:**
- Modify: `invoice/sales/models.py` (append)
- Modify: `invoice/sales/admin.py`

**Step 1: Add models**

Append to `invoice/sales/models.py`:

```python
class TripReconciliation(models.Model):
    trip = models.OneToOneField('Trip', on_delete=models.CASCADE, related_name='reconciliation')
    reconciled_by = models.CharField(max_length=200, blank=True, null=True)
    date_reconciled = models.DateTimeField(blank=True, null=True)
    return_to_warehouse = models.BooleanField(default=True, help_text="Return unsold goods to warehouse?")

    def __str__(self):
        return f"Reconciliation for Trip {self.trip.uniqueId}"

    def save(self, *args, **kwargs):
        if not self.date_reconciled:
            self.date_reconciled = timezone.localtime(timezone.now())
        super().save(*args, **kwargs)


class TripReconciliationLine(models.Model):
    reconciliation = models.ForeignKey('TripReconciliation', on_delete=models.CASCADE, related_name='lines')
    service = models.ForeignKey('Service', on_delete=models.PROTECT)
    quantity_remaining = models.DecimalField(max_digits=15, decimal_places=3)
    quantity_sold = models.DecimalField(max_digits=15, decimal_places=3, default=0, help_text="Auto-calculated: loaded - remaining")

    def __str__(self):
        return f"{self.service.title}: {self.quantity_remaining} remaining, {self.quantity_sold} sold"
```

**Step 2: Register in admin, migrate, commit**

```bash
python manage.py makemigrations sales && python manage.py migrate
git add invoice/sales/models.py invoice/sales/admin.py invoice/sales/migrations/
git commit -m "feat: add TripReconciliation and TripReconciliationLine models"
```

---

## Task 6: Add StockAdjustment model

**Files:**
- Modify: `invoice/sales/models.py` (append)
- Modify: `invoice/sales/admin.py`

**Step 1: Add model**

Append to `invoice/sales/models.py`:

```python
class StockAdjustment(models.Model):
    REASON_CHOICES = [
        ('MANUAL_RESTOCK', 'Manual Restock'),
        ('DAMAGE', 'Damage/Loss'),
        ('CORRECTION', 'Inventory Correction'),
        ('RETURN_FROM_TRUCK', 'Return from Truck'),
        ('OTHER', 'Other'),
    ]

    supply = models.ForeignKey('Supply', on_delete=models.CASCADE, related_name='adjustments')
    quantity_change = models.DecimalField(max_digits=15, decimal_places=3, help_text="Positive=add, Negative=remove")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='MANUAL_RESTOCK')
    notes = models.TextField(blank=True, null=True)
    uniqueId = models.CharField(max_length=100, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        sign = "+" if self.quantity_change > 0 else ""
        return f"{self.supply.name}: {sign}{self.quantity_change} ({self.get_reason_display()})"

    def save(self, *args, **kwargs):
        if not self.date_created:
            self.date_created = timezone.localtime(timezone.now())
        if not self.uniqueId:
            self.uniqueId = f"ADJ-{uuid4().hex[:8]}"
        super().save(*args, **kwargs)
```

**Step 2: Register in admin, migrate, commit**

```bash
python manage.py makemigrations sales && python manage.py migrate
git add invoice/sales/models.py invoice/sales/admin.py invoice/sales/migrations/
git commit -m "feat: add StockAdjustment model for warehouse restocking and corrections"
```

---

## Task 7: Enhance Purchase to auto-restock on RECEIVED

**Files:**
- Modify: `invoice/sales/views.py` (wherever purchase status is changed to RECEIVED/CONFIRMED)

**Step 1: Find the purchase_confirm view**

Look for the `purchase_confirm` view in `invoice/sales/views.py`. Add stock increment logic:

```python
# Inside purchase_confirm view, after setting status to CONFIRMED/RECEIVED:
from django.db import transaction as db_transaction

with db_transaction.atomic():
    purchase.status = 'RECEIVED'
    purchase.save()
    # Auto-increment warehouse stock
    for line in purchase.purchase_lines.all():
        supply = line.supply
        supply.stock_quantity += line.quantity
        supply.save()
```

**Step 2: Commit**

```bash
git add invoice/sales/views.py
git commit -m "feat: auto-restock warehouse when purchase status is RECEIVED"
```

---

## Task 8: Truck management views and templates

**Files:**
- Modify: `invoice/sales/views.py` (add truck views)
- Modify: `invoice/sales/urls.py` (add truck URLs)
- Create: `invoice/templates/sales/trucks.html` (truck list + create/edit)
- Create: `invoice/templates/sales/truck_detail.html` (truck inventory view)

**Step 1: Add truck views**

Add to `invoice/sales/views.py`:

```python
@login_required
def trucks_list(request):
    trucks = Truck.objects.filter(is_active=True)
    context = {'trucks': trucks}
    return render(request, 'sales/trucks.html', context)

@login_required
def truck_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        plate_number = request.POST.get('plate_number', '')
        zone = request.POST.get('zone', '')
        driver_name = request.POST.get('driver_name', '')
        truck = Truck.objects.create(
            name=name, plate_number=plate_number,
            zone=zone, driver_name=driver_name
        )
        messages.success(request, f'Truck "{truck.name}" created.')
        return redirect('trucks_list')
    return render(request, 'sales/trucks.html')

@login_required
def truck_edit(request, truck_id):
    truck = get_object_or_404(Truck, pk=truck_id)
    if request.method == 'POST':
        truck.name = request.POST.get('name', truck.name)
        truck.plate_number = request.POST.get('plate_number', truck.plate_number)
        truck.zone = request.POST.get('zone', truck.zone)
        truck.driver_name = request.POST.get('driver_name', truck.driver_name)
        truck.save()
        messages.success(request, f'Truck "{truck.name}" updated.')
        return redirect('trucks_list')
    return redirect('trucks_list')

@login_required
def truck_delete(request, truck_id):
    truck = get_object_or_404(Truck, pk=truck_id)
    if request.method == 'POST':
        # Check for active trips
        if truck.trips.exclude(status='COMPLETED').exists():
            messages.error(request, 'Cannot delete truck with active trips.')
            return redirect('trucks_list')
        truck.is_active = False
        truck.save()
        messages.success(request, f'Truck "{truck.name}" deactivated.')
    return redirect('trucks_list')

@login_required
def truck_detail(request, truck_id):
    truck = get_object_or_404(Truck, pk=truck_id)
    inventory = truck.inventory_items.select_related('service').all()
    trips = truck.trips.order_by('-date_created')[:10]
    context = {'truck': truck, 'inventory': inventory, 'trips': trips}
    return render(request, 'sales/truck_detail.html', context)
```

**Step 2: Add URLs**

Add to `invoice/sales/urls.py`:

```python
# Trucks
path('trucks/', trucks_list, name='trucks_list'),
path('trucks/create/', truck_create, name='truck_create'),
path('trucks/<int:truck_id>/', truck_detail, name='truck_detail'),
path('trucks/<int:truck_id>/edit/', truck_edit, name='truck_edit'),
path('trucks/<int:truck_id>/delete/', truck_delete, name='truck_delete'),
```

**Step 3: Create templates**

Create `invoice/templates/sales/trucks.html` and `invoice/templates/sales/truck_detail.html` following the pattern of existing templates (e.g., `supplies.html`, `purchase_detail.html`). Use Bootstrap 5, crispy forms, same sidebar/layout structure.

**Step 4: Commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py invoice/templates/sales/trucks.html invoice/templates/sales/truck_detail.html
git commit -m "feat: add truck management CRUD views and templates"
```

---

## Task 9: Trip creation and loading views

**Files:**
- Modify: `invoice/sales/views.py` (add trip views)
- Modify: `invoice/sales/urls.py`
- Create: `invoice/templates/sales/trips.html` (trip list)
- Create: `invoice/templates/sales/trip_detail.html` (trip detail + all phases)

**Step 1: Add trip list and create views**

```python
@login_required
def trips_list(request):
    trips = Trip.objects.select_related('truck').all()
    context = {'trips': trips}
    return render(request, 'sales/trips.html', context)

@login_required
def trip_create(request):
    if request.method == 'POST':
        truck_id = request.POST.get('truck')
        truck = get_object_or_404(Truck, pk=truck_id, is_active=True)
        # Check no active trip for this truck
        if truck.trips.filter(status__in=['LOADING', 'IN_PROGRESS', 'RECONCILING']).exists():
            messages.error(request, f'Truck "{truck.name}" already has an active trip.')
            return redirect('trips_list')
        trip = Trip.objects.create(truck=truck)
        messages.success(request, f'Trip {trip.uniqueId} created for {truck.name}.')
        return redirect('trip_detail', trip_id=trip.pk)
    trucks = Truck.objects.filter(is_active=True)
    return render(request, 'sales/trips.html', {'trucks': trucks})
```

**Step 2: Add trip loading (confirm load) view**

```python
@login_required
def trip_detail(request, trip_id):
    trip = get_object_or_404(Trip, pk=trip_id)
    load_lines = trip.load_lines.select_related('service').all()
    sales = trip.sales.select_related('client', 'invoice').all()
    reconciliation = getattr(trip, 'reconciliation', None)
    services = Service.objects.all()
    clients = Client.objects.all()
    context = {
        'trip': trip, 'load_lines': load_lines, 'sales': sales,
        'reconciliation': reconciliation, 'services': services, 'clients': clients,
    }
    return render(request, 'sales/trip_detail.html', context)

@login_required
@require_POST
def trip_add_load_line(request, trip_id):
    trip = get_object_or_404(Trip, pk=trip_id, status='LOADING')
    service_id = request.POST.get('service')
    quantity = Decimal(request.POST.get('quantity', '0'))
    service = get_object_or_404(Service, pk=service_id)

    # Validate warehouse stock (find matching Supply by service title or link)
    # Note: In distributor context, Service items ARE the products.
    # Stock is tracked on Service-linked Supply or directly.
    # For now, we load from truck perspective - validation happens on confirm.

    load_line, created = TripLoadLine.objects.get_or_create(
        trip=trip, service=service,
        defaults={'quantity_loaded': quantity}
    )
    if not created:
        load_line.quantity_loaded += quantity
        load_line.save()

    messages.success(request, f'Added {quantity} x {service.title} to trip load.')
    return redirect('trip_detail', trip_id=trip.pk)

@login_required
@require_POST
def trip_confirm_loading(request, trip_id):
    """Confirm loading: deduct from warehouse, add to truck inventory, set IN_PROGRESS."""
    trip = get_object_or_404(Trip, pk=trip_id, status='LOADING')

    with transaction.atomic():
        for line in trip.load_lines.select_related('service').all():
            # Find warehouse supply matching this service
            # Convention: Supply.name matches Service.title, or use a FK if added later
            supplies = Supply.objects.filter(name=line.service.title)
            if not supplies.exists():
                messages.error(request, f'No warehouse supply found for "{line.service.title}".')
                return redirect('trip_detail', trip_id=trip.pk)
            supply = supplies.first()
            if supply.stock_quantity < line.quantity_loaded:
                messages.error(request, f'Insufficient stock for "{line.service.title}". Available: {supply.stock_quantity}')
                return redirect('trip_detail', trip_id=trip.pk)

            # Deduct from warehouse
            supply.stock_quantity -= line.quantity_loaded
            supply.save()

            # Add to truck inventory
            truck_inv, created = TruckInventory.objects.get_or_create(
                truck=trip.truck, service=line.service,
                defaults={'quantity': line.quantity_loaded}
            )
            if not created:
                truck_inv.quantity += line.quantity_loaded
                truck_inv.save()

        trip.status = 'IN_PROGRESS'
        trip.date_departure = timezone.localtime(timezone.now())
        trip.save()

    messages.success(request, f'Trip {trip.uniqueId} loading confirmed. Truck is now in progress.')
    return redirect('trip_detail', trip_id=trip.pk)
```

**Step 3: Add URLs**

```python
# Trips
path('trips/', trips_list, name='trips_list'),
path('trips/create/', trip_create, name='trip_create'),
path('trips/<int:trip_id>/', trip_detail, name='trip_detail'),
path('trips/<int:trip_id>/add-load/', trip_add_load_line, name='trip_add_load_line'),
path('trips/<int:trip_id>/confirm-loading/', trip_confirm_loading, name='trip_confirm_loading'),
```

**Step 4: Create templates, commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py invoice/templates/sales/trips.html invoice/templates/sales/trip_detail.html
git commit -m "feat: add trip creation, loading, and confirm-loading workflow"
```

---

## Task 10: Trip reconciliation views

**Files:**
- Modify: `invoice/sales/views.py`
- Modify: `invoice/sales/urls.py`

**Step 1: Add start-reconciliation and submit-reconciliation views**

```python
@login_required
@require_POST
def trip_start_reconciliation(request, trip_id):
    """Move trip from IN_PROGRESS to RECONCILING when truck returns."""
    trip = get_object_or_404(Trip, pk=trip_id, status='IN_PROGRESS')
    trip.status = 'RECONCILING'
    trip.date_return = timezone.localtime(timezone.now())
    trip.save()
    messages.success(request, f'Trip {trip.uniqueId} is now reconciling.')
    return redirect('trip_detail', trip_id=trip.pk)

@login_required
@require_POST
def trip_submit_reconciliation(request, trip_id):
    """
    Owner submits remaining quantities. App calculates sold.
    Expects POST data: service_<id>=remaining_quantity for each loaded service.
    Also: reconciled_by, return_to_warehouse (checkbox).
    """
    trip = get_object_or_404(Trip, pk=trip_id, status='RECONCILING')

    with transaction.atomic():
        reconciled_by = request.POST.get('reconciled_by', '')
        return_to_warehouse = request.POST.get('return_to_warehouse') == 'on'

        recon = TripReconciliation.objects.create(
            trip=trip,
            reconciled_by=reconciled_by,
            return_to_warehouse=return_to_warehouse,
        )

        for line in trip.load_lines.select_related('service').all():
            remaining = Decimal(request.POST.get(f'remaining_{line.service.pk}', '0'))
            sold = line.quantity_loaded - remaining

            TripReconciliationLine.objects.create(
                reconciliation=recon,
                service=line.service,
                quantity_remaining=remaining,
                quantity_sold=max(sold, Decimal('0')),
            )

            # Update truck inventory
            truck_inv = TruckInventory.objects.filter(
                truck=trip.truck, service=line.service
            ).first()
            if truck_inv:
                truck_inv.quantity = remaining
                if return_to_warehouse and remaining > 0:
                    # Return to warehouse
                    supply = Supply.objects.filter(name=line.service.title).first()
                    if supply:
                        supply.stock_quantity += remaining
                        supply.save()
                        StockAdjustment.objects.create(
                            supply=supply,
                            quantity_change=remaining,
                            reason='RETURN_FROM_TRUCK',
                            notes=f'Returned from Trip {trip.uniqueId}',
                        )
                    truck_inv.quantity = Decimal('0')
                truck_inv.save()

        trip.status = 'COMPLETED'
        trip.save()

    messages.success(request, f'Trip {trip.uniqueId} reconciliation complete.')
    return redirect('trip_detail', trip_id=trip.pk)
```

**Step 2: Add URLs**

```python
path('trips/<int:trip_id>/start-reconciliation/', trip_start_reconciliation, name='trip_start_reconciliation'),
path('trips/<int:trip_id>/submit-reconciliation/', trip_submit_reconciliation, name='trip_submit_reconciliation'),
```

**Step 3: Commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py
git commit -m "feat: add trip reconciliation workflow (remaining quantities, return to warehouse)"
```

---

## Task 11: Trip sales recording (client + cash) with auto-invoice

**Files:**
- Modify: `invoice/sales/views.py`
- Modify: `invoice/sales/urls.py`

**Step 1: Add trip sale views**

```python
@login_required
@require_POST
def trip_add_client_sale(request, trip_id):
    """Record a known-client sale during reconciliation. Auto-generates invoice."""
    trip = get_object_or_404(Trip, pk=trip_id, status='RECONCILING')
    client_id = request.POST.get('client')
    client = get_object_or_404(Client, pk=client_id)

    with transaction.atomic():
        # Create invoice
        invoice = Invoice.objects.create(
            client=client,
            title=f'Truck Sale - Trip {trip.uniqueId}',
            source='TRUCK_SALE',
        )

        trip_sale = TripSale.objects.create(
            trip=trip, client=client, invoice=invoice, is_cash_sale=False
        )

        # Process sale lines from POST: lines like sale_service_0, sale_qty_0, etc.
        i = 0
        while f'sale_service_{i}' in request.POST:
            service_id = request.POST.get(f'sale_service_{i}')
            qty = Decimal(request.POST.get(f'sale_qty_{i}', '0'))
            if service_id and qty > 0:
                service = get_object_or_404(Service, pk=service_id)
                unit_price = service.price or Decimal('0')

                TripSaleLine.objects.create(
                    trip_sale=trip_sale, service=service,
                    quantity=qty, unit_price=unit_price
                )

                # Add to invoice as InvoiceService
                InvoiceService.objects.create(
                    invoice=invoice, service=service,
                    units_used=int(qty), unit_price=unit_price,
                    has_fodec=service.apply_fodec,
                )
            i += 1

        # Create client transaction (DEBIT)
        total = invoice.calculate_total()
        ClientTransaction.objects.create(
            client=client, invoice=invoice,
            transaction_type='DEBIT', source='INVOICE_CREATED',
            amount=total, description=f'Truck sale - Trip {trip.uniqueId}'
        )

    messages.success(request, f'Client sale recorded. Invoice {invoice.uniqueId} generated.')
    return redirect('trip_detail', trip_id=trip.pk)

@login_required
@require_POST
def trip_add_cash_sale(request, trip_id):
    """Record anonymous/cash summary sale for trip."""
    trip = get_object_or_404(Trip, pk=trip_id, status='RECONCILING')

    with transaction.atomic():
        trip_sale = TripSale.objects.create(
            trip=trip, client=None, is_cash_sale=True,
            notes=request.POST.get('notes', 'Cash sales summary')
        )

        i = 0
        while f'cash_service_{i}' in request.POST:
            service_id = request.POST.get(f'cash_service_{i}')
            qty = Decimal(request.POST.get(f'cash_qty_{i}', '0'))
            if service_id and qty > 0:
                service = get_object_or_404(Service, pk=service_id)
                unit_price = service.price or Decimal('0')
                TripSaleLine.objects.create(
                    trip_sale=trip_sale, service=service,
                    quantity=qty, unit_price=unit_price
                )
            i += 1

    messages.success(request, 'Cash sale summary recorded.')
    return redirect('trip_detail', trip_id=trip.pk)
```

**Step 2: Add URLs**

```python
path('trips/<int:trip_id>/add-client-sale/', trip_add_client_sale, name='trip_add_client_sale'),
path('trips/<int:trip_id>/add-cash-sale/', trip_add_cash_sale, name='trip_add_cash_sale'),
```

**Step 3: Commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py
git commit -m "feat: add trip client sale (auto-invoice) and cash sale recording"
```

---

## Task 12: Walk-in sale view

**Files:**
- Modify: `invoice/sales/views.py`
- Modify: `invoice/sales/urls.py`
- Create: `invoice/templates/sales/walkin_sale.html`

**Step 1: Add walk-in sale view**

```python
@login_required
def walkin_sale_create(request):
    """Create a walk-in sale: invoice with source=WALK_IN, deducts from warehouse."""
    if request.method == 'POST':
        client_id = request.POST.get('client')  # nullable
        client = Client.objects.filter(pk=client_id).first() if client_id else None

        with transaction.atomic():
            invoice = Invoice.objects.create(
                client=client,
                title='Walk-in Sale',
                source='WALK_IN',
            )

            i = 0
            while f'service_{i}' in request.POST:
                service_id = request.POST.get(f'service_{i}')
                qty = Decimal(request.POST.get(f'qty_{i}', '0'))
                if service_id and qty > 0:
                    service = get_object_or_404(Service, pk=service_id)
                    unit_price = service.price or Decimal('0')

                    # Deduct from warehouse
                    supply = Supply.objects.filter(name=service.title).first()
                    if supply:
                        if supply.stock_quantity < qty:
                            messages.error(request, f'Insufficient stock for "{service.title}". Available: {supply.stock_quantity}')
                            # Rollback happens via atomic
                            raise ValueError("Insufficient stock")
                        supply.stock_quantity -= qty
                        supply.save()

                    InvoiceService.objects.create(
                        invoice=invoice, service=service,
                        units_used=int(qty), unit_price=unit_price,
                        has_fodec=service.apply_fodec,
                    )
                i += 1

            if client:
                total = invoice.calculate_total()
                ClientTransaction.objects.create(
                    client=client, invoice=invoice,
                    transaction_type='DEBIT', source='INVOICE_CREATED',
                    amount=total, description='Walk-in sale'
                )

        messages.success(request, f'Walk-in sale recorded. Invoice {invoice.uniqueId} created.')
        return redirect('invoice_detail', invoice_id=invoice.pk)

    services = Service.objects.all()
    clients = Client.objects.all()
    return render(request, 'sales/walkin_sale.html', {'services': services, 'clients': clients})
```

**Step 2: Add URL**

```python
path('walk-in/create/', walkin_sale_create, name='walkin_sale_create'),
```

**Step 3: Create template, commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py invoice/templates/sales/walkin_sale.html
git commit -m "feat: add walk-in sale with warehouse stock deduction"
```

---

## Task 13: Stock adjustment views

**Files:**
- Modify: `invoice/sales/views.py`
- Modify: `invoice/sales/urls.py`
- Create: `invoice/templates/sales/stock_adjustments.html`

**Step 1: Add views**

```python
@login_required
def stock_adjustments_list(request):
    adjustments = StockAdjustment.objects.select_related('supply').all()[:50]
    supplies = Supply.objects.all()
    context = {'adjustments': adjustments, 'supplies': supplies}
    return render(request, 'sales/stock_adjustments.html', context)

@login_required
@require_POST
def stock_adjustment_create(request):
    supply_id = request.POST.get('supply')
    supply = get_object_or_404(Supply, pk=supply_id)
    quantity_change = Decimal(request.POST.get('quantity_change', '0'))
    reason = request.POST.get('reason', 'MANUAL_RESTOCK')
    notes = request.POST.get('notes', '')

    with transaction.atomic():
        StockAdjustment.objects.create(
            supply=supply, quantity_change=quantity_change,
            reason=reason, notes=notes
        )
        supply.stock_quantity += quantity_change
        supply.save()

    action = "added to" if quantity_change > 0 else "removed from"
    messages.success(request, f'{abs(quantity_change)} {supply.unit} {action} {supply.name}.')
    return redirect('stock_adjustments_list')
```

**Step 2: Add URLs**

```python
path('stock-adjustments/', stock_adjustments_list, name='stock_adjustments_list'),
path('stock-adjustments/create/', stock_adjustment_create, name='stock_adjustment_create'),
```

**Step 3: Create template, commit**

```bash
git add invoice/sales/views.py invoice/sales/urls.py invoice/templates/sales/stock_adjustments.html
git commit -m "feat: add stock adjustment views for manual restocking and corrections"
```

---

## Task 14: Dashboard updates

**Files:**
- Modify: `invoice/sales/views.py` (dashboard view)
- Modify: `invoice/templates/sales/dashboard.html`

**Step 1: Add distributor stats to dashboard context**

In the existing `dashboard` view, add:

```python
# Truck & trip stats
active_trucks = Truck.objects.filter(is_active=True).count()
trucks_on_road = Trip.objects.filter(status='IN_PROGRESS').count()
trips_reconciling = Trip.objects.filter(status='RECONCILING').count()
recent_trips = Trip.objects.select_related('truck').order_by('-date_created')[:5]
low_stock_supplies = Supply.objects.filter(stock_quantity__lte=models.F('min_stock'))
```

Add these to the context dict.

**Step 2: Update dashboard template**

Add cards/sections for:
- Active trucks count
- Trucks currently on the road
- Trips awaiting reconciliation
- Recent trips table
- Low stock alerts

**Step 3: Commit**

```bash
git add invoice/sales/views.py invoice/templates/sales/dashboard.html
git commit -m "feat: add distributor stats (trucks, trips, low stock) to dashboard"
```

---

## Task 15: Navigation updates

**Files:**
- Modify: sidebar/nav template (find the base template or dashboard that contains the sidebar)

**Step 1: Identify the sidebar**

Check `invoice/templates/sales/dashboard.html` or a base template for the navigation sidebar.

**Step 2: Add navigation links**

Add to the sidebar:

```html
<!-- Distribution -->
<li class="nav-item">
    <a class="nav-link" href="{% url 'trucks_list' %}">Trucks</a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{% url 'trips_list' %}">Trips</a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{% url 'walkin_sale_create' %}">Walk-in Sale</a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{% url 'stock_adjustments_list' %}">Stock Adjustments</a>
</li>
```

**Step 3: Commit**

```bash
git add invoice/templates/
git commit -m "feat: add truck, trips, walk-in, stock adjustment links to navigation"
```

---

## Task 16: Final integration testing

**Step 1: Run migrations from scratch**

```bash
python manage.py makemigrations && python manage.py migrate
```

**Step 2: Manual test checklist**

- [ ] Create a truck with name, plate, zone, driver
- [ ] Create a trip for that truck
- [ ] Add load lines (products + quantities)
- [ ] Confirm loading → verify warehouse stock decreased, truck inventory increased
- [ ] Start reconciliation → enter remaining quantities
- [ ] Add a client sale → verify invoice auto-generated with correct source
- [ ] Add a cash sale summary
- [ ] Submit reconciliation with "return to warehouse" → verify stock returned
- [ ] Submit reconciliation with "keep on truck" → verify truck inventory persists
- [ ] Create a walk-in sale → verify warehouse stock decreased
- [ ] Create a stock adjustment → verify supply quantity changed
- [ ] Check dashboard shows truck/trip stats

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration testing fixes"
```
