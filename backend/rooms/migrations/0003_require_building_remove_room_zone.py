from django.db import migrations, models
import django.db.models.deletion


def require_existing_buildings(apps, schema_editor):
    Room = apps.get_model("rooms", "Room")
    missing = list(Room.objects.using(schema_editor.connection.alias).filter(
        building_id__isnull=True,
    ).values_list("code", flat=True))
    if missing:
        raise RuntimeError(
            "Assign a building to every room before applying rooms.0003. "
            "Rooms without buildings: " + ", ".join(missing)
        )


def restore_derived_zones(apps, schema_editor):
    # On rollback reconstruct the former field from its authoritative building.
    # A pre-upgrade backup is needed to restore any old conflicting overrides.
    Room = apps.get_model("rooms", "Room")
    alias = schema_editor.connection.alias
    for room in Room.objects.using(alias).select_related("building"):
        Room.objects.using(alias).filter(pk=room.pk).update(zone=room.building.campus_zone)


class Migration(migrations.Migration):
    dependencies = [("rooms", "0002_building_room_room_number_alter_room_zone_and_more")]

    operations = [
        migrations.RunPython(require_existing_buildings, restore_derived_zones),
        migrations.AlterField(
            model_name="room", name="building",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="rooms", to="rooms.building",
            ),
        ),
        migrations.RemoveField(model_name="room", name="zone"),
    ]
