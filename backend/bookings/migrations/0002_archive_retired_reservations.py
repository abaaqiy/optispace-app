from django.db import migrations, models


def archive_existing(apps, schema_editor):
    # Retired reservations must not unexpectedly block rooms when bookings return.
    apps.get_model("bookings", "Reservation").objects.using(
        schema_editor.connection.alias
    ).all().update(is_archived=True)


class Migration(migrations.Migration):
    dependencies = [("bookings", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="reservation",
            name="is_archived",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.RunPython(archive_existing, migrations.RunPython.noop),
    ]
