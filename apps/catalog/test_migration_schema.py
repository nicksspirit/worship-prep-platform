import importlib
from contextlib import nullcontext
from unittest import TestCase


class FakeCursor:
    def __init__(self):
        self.statements = []
        self._result = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        if statement.strip() == "SELECT current_schema()":
            self._result = [("wpp_catalog_v1",)]
        elif "FROM pg_catalog.pg_roles" in statement:
            self._result = []

    def fetchone(self):
        return self._result[0]

    def fetchall(self):
        return self._result


class FakeConnection:
    vendor = "postgresql"

    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return nullcontext(self._cursor)


class FakeSchemaEditor:
    def __init__(self, cursor):
        self.connection = FakeConnection(cursor)

    @staticmethod
    def quote_name(name):
        return f'"{name}"'


class EmptyApps:
    @staticmethod
    def get_models(include_auto_created=True):
        return []


class MigrationSchemaTests(TestCase):
    def test_catalog_hardening_uses_active_schema(self):
        migration = importlib.import_module(
            "apps.catalog.migrations.0004_catalog_administration"
        )
        cursor = FakeCursor()

        migration.harden_administration_tables(None, FakeSchemaEditor(cursor))

        sql = "\n".join(statement for statement, _ in cursor.statements)
        self.assertIn(
            'ALTER TABLE "wpp_catalog_v1"."catalog_catalogsongrights"', sql
        )
        self.assertNotIn("public.catalog_catalogsongrights", sql)

    def test_common_hardening_uses_active_schema(self):
        migration = importlib.import_module(
            "apps.common.migrations.0001_harden_supabase_api_exposure"
        )
        cursor = FakeCursor()

        migration.harden_supabase_api_exposure(EmptyApps(), FakeSchemaEditor(cursor))

        sql = "\n".join(statement for statement, _ in cursor.statements)
        self.assertIn(
            'ALTER TABLE IF EXISTS "wpp_catalog_v1"."django_migrations"', sql
        )
        self.assertNotIn("public.django_migrations", sql)
