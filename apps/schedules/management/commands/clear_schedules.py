"""Django management command to clear all schedule-related data."""

from django.core.management.base import BaseCommand
from django.db import connection

from apps.schedules.models import (
    Contact,
    ContentSubmission,
    ScheduleItem,
    ScheduleTemplate,
    ServiceSchedule,
    TemplateItem,
)


class Command(BaseCommand):
    """Clear all schedule-related records including Contacts."""

    help = "Delete all schedule-related records (submissions, schedule items, service schedules, template items, templates, contacts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Do not prompt for confirmation.",
        )

    def handle(self, *args, **options):
        no_input = options["no_input"]
        if not no_input:
            self.stdout.write(
                "This will delete all ContentSubmissions, ScheduleItems, ServiceSchedules, "
                "TemplateItems, ScheduleTemplates, and Contacts."
            )
            confirm = input("Are you sure? Type 'yes' to continue: ")
            if confirm != "yes":
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        with connection.cursor() as cursor:
            for model, label in [
                (ContentSubmission, "Content submissions"),
                (ScheduleItem, "Schedule items"),
                (ServiceSchedule, "Service schedules"),
                (TemplateItem, "Template items"),
                (ScheduleTemplate, "Schedule templates"),
                (Contact, "Contacts"),
            ]:
                count, _ = model.objects.all().delete()
                if count:
                    self.stdout.write(self.style.SUCCESS(f"Deleted {count} {label}."))
        self.stdout.write(self.style.SUCCESS("Schedule data cleared."))
