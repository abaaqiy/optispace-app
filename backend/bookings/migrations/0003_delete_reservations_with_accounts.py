from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0002_archive_retired_reservations"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="user",
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name="reservations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="reviewed_reservations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="cancelled_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="cancelled_reservations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
