from importlib.util import find_spec

from django.apps import apps
from django.contrib.staticfiles import finders
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase
from django.urls import reverse


class GreenfieldRuntimeTests(TestCase):
    def test_health_and_readiness_boot(self):
        self.assertEqual(self.client.get(reverse("health")).json(), {"status": "ok"})
        self.assertEqual(self.client.get(reverse("ready")).status_code, 200)

    def test_static_assets_remain_discoverable(self):
        self.assertIsNotNone(finders.find("rccgcm_logo.png"))

    def test_greenfield_modules_are_installed(self):
        self.assertEqual(apps.get_app_config("accounts").name, "apps.accounts")
        self.assertEqual(apps.get_app_config("api_keys").name, "apps.api_keys")
        self.assertEqual(apps.get_app_config("catalog").name, "apps.catalog")

    def test_legacy_modules_and_routes_are_absent(self):
        self.assertIsNone(find_spec("apps.schedules"))
        self.assertIsNone(find_spec("apps.songs"))
        for path in (
            "/schedule/",
            "/api/v1/schedules",
            "/api/v1/schedules/intake",
            "/api/v1/songs/intake",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_database_uses_only_fresh_product_migrations(self):
        loader = MigrationLoader(connection)
        migrated_apps = {app_label for app_label, _name in loader.disk_migrations}

        self.assertTrue({"accounts", "api_keys", "catalog"} <= migrated_apps)
        self.assertTrue({"users", "schedules", "songs"}.isdisjoint(migrated_apps))
