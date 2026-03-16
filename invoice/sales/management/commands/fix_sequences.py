"""Reset all auto-increment sequences for tenant schemas so inserts don't collide."""

from django.core.management.base import BaseCommand
from django.db import connection
from tenants.models import Tenant


class Command(BaseCommand):
    help = "Reset PostgreSQL sequences for all tables in all tenant schemas"

    def handle(self, *args, **options):
        for tenant in Tenant.objects.exclude(schema_name='public'):
            connection.set_tenant(tenant)
            schema = tenant.schema_name
            self.stdout.write(f"Fixing sequences for schema: {schema}")

            with connection.cursor() as cursor:
                # Find all tables with a serial/identity 'id' column
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND column_name = 'id'
                      AND column_default LIKE 'nextval%%'
                """, [schema])
                tables = [row[0] for row in cursor.fetchall()]

                for table in tables:
                    cursor.execute(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{schema}.{table}', 'id'),
                            COALESCE((SELECT MAX(id) FROM "{schema}"."{table}"), 1)
                        )
                    """)
                    self.stdout.write(f"  Reset: {table}")

        self.stdout.write(self.style.SUCCESS("Done."))
