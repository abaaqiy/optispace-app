from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from .models import AcademicSemester, TimetableImageImport


class SemesterSettingsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            'semester-admin', 'semester-admin@oauife.edu.ng', 'Test-only-472!',
        )
        self.client.force_login(self.admin)
        self.list_url = reverse('admin:scheduling_academicsemester_changelist')
        self.add_url = reverse('admin:scheduling_academicsemester_add')
        self.values = dict(academic_session='2029/2030', semester='Rain',
                           first_date='2030-01-07', last_date='2030-01-21', exclude_dates='2030-01-14')

    def test_admin_configures_and_edits_shared_settings_inside_timetables(self):
        timetables = self.client.get(reverse('admin:scheduling_timetableday_changelist'))
        self.assertContains(timetables, self.list_url)
        self.assertContains(self.client.get(self.list_url), 'Already imported classes keep their saved dates')
        response = self.client.post(self.add_url, {**self.values, '_save': 'Save'})
        self.assertRedirects(response, self.list_url)
        semester = AcademicSemester.objects.get()
        self.assertEqual(semester.first_date, date(2030, 1, 7))
        url = reverse('admin:scheduling_academicsemester_change', args=[semester.pk])
        response = self.client.post(url, {**self.values, 'last_date': '2030-02-01', '_save': 'Save'})
        self.assertRedirects(response, self.list_url)
        semester.refresh_from_db()
        self.assertEqual(semester.last_date, date(2030, 2, 1))
        index = self.client.get(reverse('admin:index'))
        app = next(app for app in index.context['app_list'] if app['app_label'] == 'scheduling')
        self.assertEqual({model['object_name'] for model in app['models']}, {'Course', 'TimetableDay'})

    def test_invalid_periods_breaks_and_duplicate_semesters_are_rejected(self):
        cases = [
            {'last_date': '2030-01-01'}, {'last_date': '2032-01-01'},
            {'exclude_dates': 'not-a-date'}, {'exclude_dates': '2030-02-01'},
            {'academic_session': '   '}, {'semester': 'Unrecognised'},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                response = self.client.post(self.add_url, {**self.values, **changes, '_save': 'Save'})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['adminform'].form.errors)
                self.assertFalse(AcademicSemester.objects.exists())
        AcademicSemester.objects.create(**self.values)
        duplicate = self.client.post(self.add_url, {**self.values, '_save': 'Save'})
        self.assertTrue(duplicate.context['adminform'].form.errors)
        self.assertEqual(AcademicSemester.objects.count(), 1)

    def test_model_normalises_dates_and_validates_non_admin_writes(self):
        semester = AcademicSemester.objects.create(**{**self.values, 'academic_session': ' 2029/2030 ',
                                                      'exclude_dates': '2030-01-14, 2030-01-07\n2030-01-14'})
        self.assertEqual(semester.academic_session, '2029/2030')
        self.assertEqual(semester.exclude_dates, '2030-01-07, 2030-01-14')
        semester.last_date = date(2030, 1, 1)
        with self.assertRaises(ValidationError):
            semester.save()

    def test_settings_require_separate_permissions_and_csrf(self):
        for role in ('student', 'lecturer'):
            user = get_user_model().objects.create_user(
                username=f'semester-{role}', email=f'{role}@student.oauife.edu.ng' if role == 'student' else 'lecturer@oauife.edu.ng', role=role,
            )
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.list_url).status_code, 302)
        staff = get_user_model().objects.create_user(
            username='semester-staff', email='staff@oauife.edu.ng', role='lecturer', is_staff=True,
        )
        staff.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='scheduling', codename__in=['add_timetableday', 'change_timetableday'],
        ))
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.client.post(self.add_url, self.values).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:scheduling_timetableday_document')).status_code, 200)
        staff.user_permissions.add(Permission.objects.get(
            content_type__app_label='scheduling', codename='view_academicsemester',
        ))
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.assertEqual(self.client.post(self.add_url, self.values).status_code, 403)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(self.add_url, self.values).status_code, 403)
        self.assertFalse(AcademicSemester.objects.exists())

    def test_used_settings_cannot_be_deleted_and_import_snapshot_is_preserved(self):
        semester = AcademicSemester.objects.create(**self.values)
        source = TimetableImageImport.objects.create(filename='old.jpg', teaching_semester=semester, **self.values)
        with self.assertRaises(ProtectedError):
            semester.delete()
        semester.last_date = date(2030, 2, 1)
        semester.save()
        source.refresh_from_db()
        self.assertEqual(source.last_date, date(2030, 1, 21))
