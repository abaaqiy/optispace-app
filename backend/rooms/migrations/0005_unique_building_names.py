import re

from django.db import migrations, models


def populate_names(apps, schema_editor):
    Building = apps.get_model('rooms', 'Building')
    changes, used, conflicts = [], {}, []
    for building in Building.objects.using(schema_editor.connection.alias).order_by('pk'):
        key = re.sub(r'[^a-z0-9]', '', building.name.casefold())
        if not key:
            conflicts.append(f'empty name on building #{building.pk}')
        elif key in used:
            conflicts.append(f'{used[key]} / {building.name}')
        else:
            used[key] = building.name
        building.name_key = key
        changes.append(building)
    if conflicts:
        raise RuntimeError('Resolve duplicate building names before rooms.0005: ' + ', '.join(conflicts))
    Building.objects.using(schema_editor.connection.alias).bulk_update(changes, ['name_key'])


class Migration(migrations.Migration):
    dependencies = [('rooms', '0004_unique_room_names')]
    operations = [
        migrations.AddField(model_name='building', name='name_key',
                            field=models.CharField(default='', max_length=400, editable=False), preserve_default=False),
        migrations.RunPython(populate_names, migrations.RunPython.noop),
        migrations.AlterField(model_name='building', name='name_key',
                              field=models.CharField(max_length=400, unique=True, editable=False)),
        migrations.AddConstraint(model_name='building', constraint=models.CheckConstraint(
            condition=~models.Q(name_key=''), name='building_name_key_required')),
        migrations.AddConstraint(model_name='building', constraint=models.UniqueConstraint(
            models.Func(models.functions.Lower('name'), models.Value('[^a-z0-9]'), models.Value(''),
                        models.Value('g'), function='REGEXP_REPLACE', output_field=models.CharField()),
            name='building_name_normalised_unique')),
    ]
