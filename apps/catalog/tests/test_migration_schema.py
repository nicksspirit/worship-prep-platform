"""Verify the custom operations retained in the regenerated migrations."""

from django.apps import apps
from django.db import connection
from django.test import TestCase


class MigrationSchemaTests(TestCase):
    def test_all_application_tables_enable_row_level_security(self):
        tables = {
            model._meta.db_table
            for model in apps.get_models(include_auto_created=True)
            if model._meta.managed
        } | {"django_migrations"}

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relname, relrowsecurity FROM pg_class "
                "WHERE relnamespace = current_schema()::regnamespace "
                "AND relname = ANY(%s)",
                [sorted(tables)],
            )
            security = dict(cursor.fetchall())

        self.assertEqual(set(security), tables)
        self.assertTrue(all(security.values()))

    def test_catalog_search_configuration_removes_accents(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_tsvector('public.wpp_simple_unaccent', 'café')::text"
            )
            vector = cursor.fetchone()[0]

        self.assertEqual(vector, "'cafe':1")

    def test_catalog_search_indexes_exist(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND tablename = 'catalog_catalogentry'"
            )
            indexes = {row[0] for row in cursor.fetchall()}

        self.assertTrue(
            {
                "catalog_title_fts_gin", "catalog_lyrics_fts_gin",
                "catalog_title_trgm_gin", "catalog_page_order_idx",
            } <= indexes
        )
