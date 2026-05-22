"""Batch-poll TTN for acknowledgements on pending elfatoora submissions.

Cron-friendly: iterates over all tenant schemas, polls every GovInvoice in
SUBMITTED state, updates status based on TTN response. Designed to run every
few minutes.

Usage:
    python manage.py poll_elfatoora                # poll across all tenants
    python manage.py poll_elfatoora --schema TENANT  # poll one tenant only
    python manage.py poll_elfatoora --dry-run       # log only, no DB writes
"""
import logging
from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Poll TTN/elfatoora for status updates on SUBMITTED invoices.'

    def add_arguments(self, parser):
        parser.add_argument('--schema', help='Limit to a single tenant schema.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Skip writes; log what would happen.')

    def handle(self, *args, schema=None, dry_run=False, **opts):
        from tenants.models import Tenant
        from gov.models import GovInvoice
        from gov.elfatoora.service import poll
        from gov.elfatoora.client import ElfatooraError

        original_schema = connection.schema_name

        try:
            connection.set_schema_to_public()
            if schema:
                tenants = list(Tenant.objects.filter(schema_name=schema))
            else:
                tenants = list(Tenant.objects.exclude(schema_name='public'))

            totals = {'polled': 0, 'updated': 0, 'errors': 0}

            for tenant in tenants:
                connection.set_schema(tenant.schema_name)
                pending = GovInvoice.objects.filter(elfatoora_status='SUBMITTED')
                self.stdout.write(
                    f'[{tenant.schema_name}] {pending.count()} pending invoice(s)'
                )
                for gi in pending:
                    totals['polled'] += 1
                    if dry_run:
                        self.stdout.write(f'  - would poll GovInvoice {gi.id}')
                        continue
                    try:
                        prev = gi.elfatoora_status
                        poll(gi)
                        if gi.elfatoora_status != prev:
                            totals['updated'] += 1
                            self.stdout.write(
                                f'  - GovInvoice {gi.id}: {prev} -> {gi.elfatoora_status}'
                            )
                    except ElfatooraError as e:
                        totals['errors'] += 1
                        logger.warning(
                            f'[{tenant.schema_name}] poll failed for {gi.id}: {e}'
                        )
        finally:
            connection.set_schema(original_schema)

        self.stdout.write(self.style.SUCCESS(
            f'Done. polled={totals["polled"]} '
            f'updated={totals["updated"]} errors={totals["errors"]}'
        ))
