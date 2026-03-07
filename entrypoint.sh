#!/bin/sh
set -e

# If arguments are passed to the script (like "bash" or "python"), run those instead
if [ $# -gt 0 ]; then
    exec "$@"
fi

# ----------------------------------------------------------------
# OPTIONAL: Make Migrations
# This generates new migration files based on model changes.
# NOTE: The container user must have WRITE access to the app folders.
# ----------------------------------------------------------------
echo "Checking for model changes..."
python manage.py makemigrations --noinput || echo "Make migrations failed (possibly permission error), skipping..."

# ----------------------------------------------------------------
# Wait for Database to be ready
# ----------------------------------------------------------------
echo "Waiting for database..."
until python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
print('Database is ready.')
" 2>/dev/null; do
  echo "Database not ready yet. Retrying in 3 seconds..."
  sleep 3
done

# ----------------------------------------------------------------
# Fix migration history: ensure all sales migrations are recorded
# so that cross-app dependencies (payment, gov) are satisfied.
# This is safe to run repeatedly — it only inserts missing records.
# Remove this block once all environments are stable.
# ----------------------------------------------------------------
echo "Fixing migration history..."
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice.settings')
django.setup()

from django.db import connection
from django_tenants.utils import get_tenant_model

SALES_MIGRATIONS = [
    '0001_initial',
    '0002_alter_settings_options_alter_invoice_timbre_fiscal_and_more',
    '0003_invoice_is_locked',
    '0004_client_status_settings_status',
    '0005_supplier',
    '0006_settings_rib',
    '0007_rename_service_invoiceservice_item_and_more',
    '0008_rename_item_invoiceservice_services',
    '0009_rename_services_invoiceservice_invoice_services',
    '0010_rename_invoice_services_invoiceservice_services_and_more',
    '0011_rename_item_type_service_service_type',
    '0012_rename_services_invoiceservice_service',
    '0013_clienttransaction',
    '0014_purchase_suppliertransaction_supply_purchaseline_and_more',
    '0015_purchaseline_has_fodec_supply_apply_fodec',
    '0016_invoice_amount_paid',
    '0017_alter_settings_clientlogo',
    '0018_settings_emailaddress_settings_phone',
    '0019_alter_clienttransaction_source_creditnote',
    '0020_clienttransaction_credit_note',
    '0021_settings_default_retenu_rate',
    '0022_bon_livraison',
]

def fix_schema(schema_name):
    cursor = connection.cursor()
    cursor.execute(f'SET search_path TO \"{schema_name}\"')
    for mig in SALES_MIGRATIONS:
        cursor.execute(
            \"\"\"INSERT INTO django_migrations (app, name, applied)
               SELECT 'sales', %s, NOW()
               WHERE NOT EXISTS (
                   SELECT 1 FROM django_migrations WHERE app='sales' AND name=%s
               )\"\"\",
            [mig, mig]
        )

# Fix public schema
fix_schema('public')

# Fix each tenant schema
for tenant in get_tenant_model().objects.exclude(schema_name='public'):
    fix_schema(tenant.schema_name)

# Reset search_path
connection.cursor().execute('SET search_path TO public')

print('Migration history fixed.')
"

# ----------------------------------------------------------------
# Run Migrations
# ----------------------------------------------------------------
echo "Running shared migrations..."
python manage.py migrate_schemas --shared --noinput

echo "Running tenant migrations..."
python manage.py migrate_schemas --noinput

# ----------------------------------------------------------------
# Collect Static Files
# ----------------------------------------------------------------
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || echo "Collectstatic failed, continuing..."

# ----------------------------------------------------------------
# Start Server
# ----------------------------------------------------------------
echo "Starting gunicorn..."
exec gunicorn invoice.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --log-level warning