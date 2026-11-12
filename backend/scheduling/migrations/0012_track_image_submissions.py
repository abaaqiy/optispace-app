from datetime import datetime
import re
import unicodedata

import django.db.models.deletion
from django.db import migrations, models


def department_key(value):
    text = unicodedata.normalize('NFKC', str(value or '')).lower()
    text = re.sub(r'\([^)]*\)', '', text).replace('&', ' and ')
    text = re.sub(r'[^a-z0-9]+', ' ', text).strip()
    text = re.sub(r'^(?:(?:the )?(?:department|dept|faculty|school)(?: of)?\s+)+', '', text)
    text = re.sub(r'^(?:b sc|bsc|b eng|beng|b a|ba|ll b|llb)\s+', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def preserve_submissions(apps, schema_editor):
    alias = schema_editor.connection.alias
    Import = apps.get_model('scheduling', 'TimetableImageImport')
    Draft = apps.get_model('scheduling', 'TimetableImageDraft')
    Submission = apps.get_model('scheduling', 'TimetableImageSubmission')
    history = []
    for draft in Draft.objects.using(alias).only('filename', 'document'):
        document = draft.document
        if not isinstance(document, dict):
            continue
        options = document.get('review_options', {})
        for batch in document.get('imported_batches', []):
            if batch.get('view') not in {'all', 'unassigned', '1', '2', '3', '4', '5', '6'}:
                continue
            try:
                when = datetime.fromisoformat(batch['imported_at'])
                if when.tzinfo is None:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            history.append((draft.filename, department_key(options.get('department', '')),
                            str(options.get('teaching_semester', '')), when, batch['view']))
    for source in Import.objects.using(alias).order_by('created_at', 'pk'):
        key = department_key(source.department)
        if not key or not source.academic_session or not source.semester:
            continue
        # The first selected-Part release saved its scope in the continuing
        # draft. Match the filename, department, semester and confirmation time
        # to preserve that Part without claiming its unsubmitted levels.
        candidates = {view for filename, department, semester, when, view in history
                      if filename == source.filename and department == key
                      and semester == str(source.teaching_semester_id)
                      and abs((when - source.created_at).total_seconds()) <= 120}
        view = candidates.pop() if len(candidates) == 1 else 'all'
        Import.objects.using(alias).filter(pk=source.pk).update(review_scope=view)
        parts = range(7) if view == 'all' else [0 if view == 'unassigned' else int(view)]
        Submission.objects.using(alias).bulk_create([
            Submission(department_key=key, academic_session=re.sub(r'\s+', '', source.academic_session),
                       semester=source.semester.strip().title(), part=part, image_import_id=source.pk)
            for part in parts
        ], ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [('scheduling', '0011_unique_course_codes')]
    operations = [
        migrations.AddField(model_name='timetableimageimport', name='review_scope',
                            field=models.CharField(default='all', max_length=10, editable=False)),
        migrations.CreateModel(
            name='TimetableImageSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('department_key', models.CharField(max_length=400)),
                ('academic_session', models.CharField(max_length=30)),
                ('semester', models.CharField(max_length=20)),
                ('part', models.PositiveSmallIntegerField()),
                ('image_import', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                   related_name='submissions', to='scheduling.timetableimageimport')),
            ],
            options={'constraints': [
                models.UniqueConstraint(fields=('department_key', 'academic_session', 'semester', 'part'),
                                        name='unique_department_timetable_part'),
                models.CheckConstraint(condition=models.Q(part__lte=6), name='timetable_submission_part_valid'),
                models.CheckConstraint(condition=~models.Q(department_key=''), name='timetable_submission_department_required'),
            ]},
        ),
        migrations.RunPython(preserve_submissions, migrations.RunPython.noop),
    ]
