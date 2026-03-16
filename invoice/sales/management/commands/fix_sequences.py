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
                # Find ALL sequences in this schema and reset them
                cursor.execute("""
                    SELECT sequence_name
                    FROM information_schema.sequences
                    WHERE sequence_schema = %s
                """, [schema])
                sequences = [row[0] for row in cursor.fetchall()]

                for seq in sequences:
                    # Extract table name from sequence (convention: tablename_id_seq)
                    table = seq.replace('_id_seq', '')
                    try:
                        cursor.execute(f"""
                            SELECT setval(
                                '"{schema}"."{seq}"',
                                COALESCE((SELECT MAX(id) FROM "{schema}"."{table}"), 1)
                            )
                        """)
                        self.stdout.write(f"  Reset: {seq}")
                    except Exception as e:
                        self.stdout.write(f"  Skipped {seq}: {e}")
                        connection.cursor()  # reset connection after error

        self.stdout.write(self.style.SUCCESS("Done."))
