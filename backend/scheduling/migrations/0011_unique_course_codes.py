import re

from django.db import migrations, models


def normalise_course_codes(apps, schema_editor):
    Course = apps.get_model('scheduling', 'Course')
    query = Course.objects.using(schema_editor.connection.alias)
    changes, used, duplicates = [], {}, []
    for course in query.order_by('pk').only('pk', 'code'):
        code = re.sub(r'\s+', '', course.code).upper()
        if not code:
            raise RuntimeError('Enter a course code before scheduling.0011.')
        if code in used:
            duplicates.append(f'{used[code]} / {course.code}')
        used[code] = course.code
        changes.append((course.pk, code))
    if duplicates:
        raise RuntimeError('Resolve duplicate course codes before scheduling.0011: ' + ', '.join(duplicates))
    for pk, code in changes:
        query.filter(pk=pk).update(code=code)


class Migration(migrations.Migration):
    dependencies = [('scheduling', '0010_shared_teaching_semesters')]

    operations = [
        migrations.RunPython(normalise_course_codes, migrations.RunPython.noop),
        migrations.AddConstraint(model_name='course', constraint=models.UniqueConstraint(
            models.functions.Upper(models.Func(
                'code', models.Value(r'\s+'), models.Value(''), models.Value('g'),
                function='REGEXP_REPLACE', output_field=models.CharField(),
            )), name='course_code_normalised_unique',
        )),
    ]
