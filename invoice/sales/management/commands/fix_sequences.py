"""Reset all auto-increment sequences for tenant schemas so inserts don't collide."""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection
from tenants.models import Tenant


class Command(BaseCommand):
    help = "Reset PostgreSQL sequences for all tables in all tenant schemas"

    def handle(self, *args, **options):
        style = no_style()
        for tenant in Tenant.objects.exclude(schema_name='public'):
            connection.set_tenant(tenant)
            schema = tenant.schema_name
            self.stdout.write(f"\nFixing sequences for schema: {schema}")

            # Get all models from tenant apps
            all_models = apps.get_models()

            # Use Django's built-in sequence reset SQL generation
            from django.db.backends.postgresql.operations import DatabaseOperations
            ops = DatabaseOperations(connection)
            sql_list = ops.sequence_reset_sql(style, all_models)

            with connection.cursor() as cursor:
                for sql in sql_list:
                    self.stdout.write(f"  Running: {sql[:80]}...")
                    cursor.execute(sql)

            self.stdout.write(self.style.SUCCESS(f"  Fixed {len(sql_list)} sequences"))

        self.stdout.write(self.style.SUCCESS("\nDone."))
