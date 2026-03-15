from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schedules", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="scheduleitem",
            constraint=models.UniqueConstraint(
                fields=("schedule", "item_type"),
                name="unique_schedule_item_type",
            ),
        ),
    ]
