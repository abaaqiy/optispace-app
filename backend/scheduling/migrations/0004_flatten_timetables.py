import django.db.models.deletion
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError


def move_classes_to_timetables(apps, schema_editor):
    Day = apps.get_model("scheduling", "TimetableDay")
    Lecture = apps.get_model("scheduling", "Allocation")
    alias = schema_editor.connection.alias
    for day in Day.objects.using(alias).all().iterator():
        entries = list(Lecture.objects.using(alias).filter(
            timetable_id=day.pk, is_cancelled=False,
        ).order_by("start_time", "pk"))
        # Check before converting, including any rows previously entered via SQL.
        for index, entry in enumerate(entries):
            if entry.start_time >= entry.end_time or (
                index and entry.start_time < entries[index - 1].end_time
            ):
                raise RuntimeError(f"Timetable {day.pk} has invalid or overlapping classes. Correct it before migrating.")
        # No separate title/cancellation/day-coverage fields remain. The upgrade
        # procedure backs up these historical values before running migrations.
        Lecture.objects.using(alias).filter(timetable_id=day.pk).delete()
        if not entries:
            Day.objects.using(alias).filter(pk=day.pk).delete()
            continue
        for index, entry in enumerate(entries):
            values = dict(
                room_id=day.room_id, date=day.date,
                start_time=entry.start_time, end_time=entry.end_time,
                course_id=entry.course_id, academic_session=entry.academic_session,
            )
            if index == 0:
                Day.objects.using(alias).filter(pk=day.pk).update(**values)
            else:
                Day.objects.using(alias).create(**values)


def reverse_empty_database_only(apps, schema_editor):
    Day = apps.get_model("scheduling", "TimetableDay")
    if Day.objects.using(schema_editor.connection.alias).exists():
        raise IrreversibleError("Restore the pre-upgrade timetable backup to recover lecture titles, cancellations and day coverage.")


class Migration(migrations.Migration):
    dependencies = [("scheduling", "0003_simplify_timetables")]

    operations = [
        migrations.RemoveConstraint(model_name="timetableday", name="unique_room_timetable_date"),
        migrations.RemoveConstraint(model_name="timetableday", name="timetable_coverage_start_before_end"),
        migrations.RenameField(model_name="timetableday", old_name="coverage_start", new_name="start_time"),
        migrations.RenameField(model_name="timetableday", old_name="coverage_end", new_name="end_time"),
        migrations.AddField(
            model_name="timetableday", name="course",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="timetables", to="scheduling.course"),
        ),
        migrations.AddField(model_name="timetableday", name="academic_session", field=models.CharField(blank=True, max_length=30)),
        migrations.RunPython(move_classes_to_timetables, reverse_empty_database_only),
        # PostgreSQL must finish deferred FK checks before altering tables again.
        migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE", migrations.RunSQL.noop),
        migrations.DeleteModel(name="Allocation"),
        migrations.AlterModelOptions(
            name="timetableday",
            options={"ordering": ["date", "start_time", "room__code"], "verbose_name": "Timetable", "verbose_name_plural": "Timetables"},
        ),
        migrations.AddConstraint(
            model_name="timetableday",
            constraint=models.CheckConstraint(condition=models.Q(start_time__lt=models.F("end_time")), name="timetable_start_before_end"),
        ),
    ]
