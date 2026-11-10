from datetime import timedelta

from django.db import migrations
from django.db.models import F
from django.utils import timezone


def extend_active_drafts(apps, schema_editor):
    Draft = apps.get_model('scheduling', 'TimetableImageDraft')
    Draft.objects.using(schema_editor.connection.alias).filter(
        expires_at__gt=timezone.now(),
        expires_at__lt=F('saved_at') + timedelta(hours=24),
    ).update(expires_at=F('saved_at') + timedelta(hours=24))


class Migration(migrations.Migration):
    dependencies = [('scheduling', '0008_persistent_image_drafts')]
    operations = [migrations.RunPython(extend_active_drafts, migrations.RunPython.noop)]
