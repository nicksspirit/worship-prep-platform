"""Exercise the explicit API rejection through Django's migration interface."""

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from apps.accounts.models import User


class SupabaseApiPolicyTests(TestCase):
    def setUp(self):
        call_command("migrate", "common", "0001", verbosity=0)
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolname FROM pg_roles")
            existing = {row[0] for row in cursor.fetchall()}
            for role in ("anon", "authenticated"):
                if role not in existing:
                    cursor.execute(f"CREATE ROLE {connection.ops.quote_name(role)}")
        call_command("migrate", "common", "0002", verbosity=0)
        User.objects.create_user(
            "rls@example.test", "test-only-password", first_name="Policy", last_name="Test"
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "GRANT SELECT ON public.accounts_user TO anon, authenticated"
            )
            cursor.execute(
                "CREATE POLICY test_allow_select ON public.accounts_user "
                "FOR SELECT TO anon, authenticated USING (true)"
            )

    def test_rejection_blocks_anonymous_reads_despite_permissive_policy(self):
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE anon")
            try:
                cursor.execute("SELECT count(*) FROM public.accounts_user")
                count = cursor.fetchone()[0]
            finally:
                cursor.execute("RESET ROLE")

        self.assertEqual(count, 0)
        self.assertEqual(User.objects.count(), 1)

    def test_rejection_blocks_authenticated_reads_despite_permissive_policy(self):
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE authenticated")
            try:
                cursor.execute("SELECT count(*) FROM public.accounts_user")
                count = cursor.fetchone()[0]
            finally:
                cursor.execute("RESET ROLE")

        self.assertEqual(count, 0)
        self.assertEqual(User.objects.count(), 1)

    def test_rejection_covers_all_commands_on_all_application_tables(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT cmd, permissive, roles, qual, with_check FROM pg_policies "
                "WHERE schemaname='public' AND policyname='deny_supabase_api'"
            )
            policies = cursor.fetchall()

        self.assertEqual(len(policies), 29)
        for command, permissive, roles, using, check in policies:
            self.assertEqual(command, "ALL")
            self.assertEqual(permissive, "RESTRICTIVE")
            self.assertEqual(set(roles), {"anon", "authenticated"})
            self.assertEqual(using, "false")
            self.assertEqual(check, "false")
