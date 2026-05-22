"""Batch-refresh NGSign status for in-flight invoices.

Moved out of the `ngsign_pending_api` view: that endpoint is polled by every
client every 30s, and doing synchronous NGSign HTTP (TIMEOUT=30s) per invoice
inside it starved web workers on prod. Run this from cron instead.

Usage:
    python manage.py refresh_ngsign                  # all tenants
    python manage.py refresh_ngsign --schema TENANT  # one tenant
"""
import logging
from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger(__name__)

ACTIVE_SIGNING = ['CREATED', 'CONFIGURED', 'SIGNED', 'MIXED']


class Command(BaseCommand):
    help = 'Refresh NGSign status for invoices currently being signed.'

    def add_arguments(self, parser):
        parser.add_argument('--schema', help='Limit to a single tenant schema.')

    def handle(self, *args, schema=None, **opts):
        from tenants.models import Tenant
        from gov.models import GovInvoice
        from gov.ngsign.service import check_status
        from gov.ngsign.exceptions import NGSignError

        original_schema = connection.schema_name
        totals = {'checked': 0, 'errors': 0}

        try:
            connection.set_schema_to_public()
            if schema:
                tenants = list(Tenant.objects.filter(schema_name=schema))
            else:
                tenants = list(Tenant.objects.exclude(schema_name='public'))

            for tenant in tenants:
                connection.set_schema(tenant.schema_name)
                pending = (
                    GovInvoice.objects
                    .filter(ngsign_status__in=ACTIVE_SIGNING)
                    .exclude(ngsign_invoice_uuid__isnull=True)
                    .exclude(ngsign_invoice_uuid='')
                )
                self.stdout.write(
                    f'[{tenant.schema_name}] {pending.count()} in-flight invoice(s)'
                )
                for gi in pending:
                    totals['checked'] += 1
                    try:
                        check_status(gi)
                    except NGSignError as e:
                        totals['errors'] += 1
                        logger.warning(
                            f'[{tenant.schema_name}] check_status failed for {gi.id}: {e}'
                        )
        finally:
            connection.set_schema(original_schema)

        self.stdout.write(self.style.SUCCESS(
            f'Done. checked={totals["checked"]} errors={totals["errors"]}'
        ))
