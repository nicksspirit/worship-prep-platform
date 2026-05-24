"""Authenticate a DB-backed integration API key from the command line."""

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandError
from django_bolt import JSON

from apps.users.api_keys import authorize_api_key


class Command(BaseCommand):
    help = "Authenticate an integration API key and print its resolved metadata."

    def add_arguments(self, parser):
        parser.add_argument(
            "api_key",
            help="Plaintext API key to authenticate.",
        )
        parser.add_argument(
            "--scope",
            action="append",
            default=[],
            help="Required scope to enforce. Repeat for multiple scopes.",
        )

    def handle(self, *args, **options):
        api_key = options["api_key"]
        required_scopes = options["scope"]

        result = async_to_sync(authorize_api_key)(
            api_key,
            required_scopes=required_scopes,
        )

        if isinstance(result, JSON):
            detail = result.data.get("detail", "Authentication failed.")
            raise CommandError(f"{detail} (status {result.status_code})")

        authenticated_key = result.api_key

        self.stdout.write(self.style.SUCCESS("API key authenticated."))
        self.stdout.write(f"Name: {authenticated_key.name}")
        self.stdout.write(f"Prefix: {authenticated_key.key_prefix}")
        self.stdout.write(f"Status: {authenticated_key.status}")
        self.stdout.write(
            "Scopes: "
            + (", ".join(result.scopes) if result.scopes else "none")
        )
        self.stdout.write(
            "Expires on: "
            + (
                authenticated_key.expires_on.isoformat()
                if authenticated_key.expires_on
                else "never"
            )
        )
        self.stdout.write(
            "Last used on: "
            + (
                authenticated_key.last_used_on.isoformat()
                if authenticated_key.last_used_on
                else "not yet used"
            )
        )
