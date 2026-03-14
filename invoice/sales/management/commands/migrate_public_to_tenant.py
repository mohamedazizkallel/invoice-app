"""
Management command to copy all tenant-app data from the public schema
into a target tenant's schema, then optionally wipe the public copies.

Usage:
    python manage.py migrate_public_to_tenant <schema_name> [--wipe]

    --wipe   After a successful copy, delete the rows from the public schema.
             Does NOT run by default — verify the copy first, then re-run with --wipe.

Example:
    python manage.py migrate_public_to_tenant swift_corp
    python manage.py migrate_public_to_tenant swift_corp --wipe
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


# Tables in the order they must be copied to satisfy foreign key constraints.
# Parent tables must come before child tables.
TENANT_TABLES = [
    # sales
    "sales_settings",
    "sales_client",
    "sales_supplier",
    "sales_supply",
    "sales_service",
    "sales_purchase",
    "sales_purchaseline",
    "sales_invoice",
    "sales_invoicesupplyusage",
    "sales_invoiceservice",
    "sales_clienttransaction",
    "sales_suppliertransaction",
    "sales_creditnote",
    "sales_bonlivraison",
    "sales_bonlivraisonline",
    "sales_devis",
    # payment
    "payment_retenu",
    "payment_invoiceretenu",
    "payment_purchaseretenu",
    # gov
    "gov_govinvoice",
]

# Tables to skip when wiping — sequences and shared lookup data
WIPE_SKIP = set()


class Command(BaseCommand):
    help = "Copy public-schema tenant data into a target tenant schema."

    def add_arguments(self, parser):
        parser.add_argument("schema_name", help="Target tenant schema name")
        parser.add_argument(
            "--wipe",
            action="store_true",
            default=False,
            help="Delete public-schema rows after copying (verify copy first).",
        )

    def handle(self, *args, **options):
        target = options["schema_name"]
        wipe = options["wipe"]

        # Confirm the target schema exists
        with connection.cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                [target],
            )
            if not cur.fetchone():
                raise CommandError(f"Schema '{target}' does not exist.")

        self.stdout.write(f"Copying public → {target} …\n")

        copied = {}
        skipped = []

        with transaction.atomic():
            with connection.cursor() as cur:
                # Disable FK checks isn't possible in PG; we rely on correct order.
                for table in TENANT_TABLES:
                    # Check table exists in public schema
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = 'public' AND table_name = %s
                        )
                        """,
                        [table],
                    )
                    if not cur.fetchone()[0]:
                        skipped.append(table)
                        continue

                    # Check table exists in target schema
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = %s AND table_name = %s
                        )
                        """,
                        [target, table],
                    )
                    if not cur.fetchone()[0]:
                        skipped.append(table)
                        self.stdout.write(
                            self.style.WARNING(f"  SKIP {table} — not in target schema")
                        )
                        continue

                    # Count rows in public
                    cur.execute(f'SELECT COUNT(*) FROM public."{table}"')
                    count = cur.fetchone()[0]

                    if count == 0:
                        self.stdout.write(f"  SKIP {table} — 0 rows")
                        continue

                    # Get column list (exclude nothing — copy everything)
                    cur.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = %s
                        ORDER BY ordinal_position
                        """,
                        [table],
                    )
                    columns = [row[0] for row in cur.fetchall()]
                    col_list = ", ".join(f'"{c}"' for c in columns)

                    # Copy rows; ON CONFLICT DO NOTHING skips already-copied rows
                    cur.execute(
                        f"""
                        INSERT INTO {target}."{table}" ({col_list})
                        SELECT {col_list} FROM public."{table}"
                        ON CONFLICT DO NOTHING
                        """
                    )
                    copied[table] = count
                    self.stdout.write(f"  COPY {table} — {count} rows")

        self.stdout.write(self.style.SUCCESS(f"\nCopy complete. {len(copied)} tables copied.\n"))

        if wipe:
            self.stdout.write("Wiping public schema rows …\n")
            with transaction.atomic():
                with connection.cursor() as cur:
                    # Delete in reverse order to respect FK constraints
                    for table in reversed(TENANT_TABLES):
                        if table in skipped or table not in copied:
                            continue
                        cur.execute(f'DELETE FROM public."{table}"')
                        self.stdout.write(f"  WIPE {table}")
            self.stdout.write(self.style.SUCCESS("Wipe complete.\n"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Rows NOT deleted from public schema.\n"
                    f"Verify data in '{target}', then re-run with --wipe.\n"
                )
            )
