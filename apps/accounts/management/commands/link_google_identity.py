from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from allauth.socialaccount.models import SocialAccount


class Command(BaseCommand):
    """Link a selected user to a stable Google provider identity."""

    help = "Create or verify a Google identity link for a selected user."

    def add_arguments(self, parser) -> None:
        """Add the identity metadata captured in the cutover record."""
        parser.add_argument("--email", required=True)
        parser.add_argument("--uid", required=True)

    def handle(self, *args, **options) -> None:
        """Create a minimal Google SocialAccount or verify the existing link."""
        user_model = get_user_model()

        with transaction.atomic():
            try:
                user = user_model.objects.select_for_update().get(
                    email__iexact=options["email"]
                )
            except user_model.DoesNotExist as error:
                raise CommandError("Selected user does not exist.") from error

            account = (
                SocialAccount.objects.select_for_update()
                .filter(provider="google", uid=options["uid"])
                .first()
            )
            if account is not None:
                if account.user != user:
                    raise CommandError("Google UID is already linked to another user.")
                created = False
            else:
                account = SocialAccount.objects.create(
                    user=user,
                    provider="google",
                    uid=options["uid"],
                    extra_data={},
                )
                created = True

        outcome = "Created" if created else "Verified"
        self.stdout.write(self.style.SUCCESS(f"{outcome} Google identity link."))
