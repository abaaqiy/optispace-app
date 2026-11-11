from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from rooms.models import Building, Room
from .forms import CourseAdminForm
from .models import Course, TimetableDay


class CourseCodeUniquenessTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(code=' csc 102 ', title='Introduction', department='Computing')

    def test_codes_are_normalised_and_manual_form_reports_duplicates(self):
        self.assertEqual(self.course.code, 'CSC102')
        for code in ('CSC102', 'csc102', 'CSC 102', ' csc\t102 '):
            with self.subTest(code=code), self.assertRaisesMessage(ValidationError, 'already exists'):
                Course.objects.create(code=code, title='Duplicate', department='Computing')
            form = CourseAdminForm(data={'code': code, 'title': 'Duplicate', 'department': 'Computing'})
            self.assertFalse(form.is_valid())
            self.assertIn('code', form.errors)
        self.assertEqual(Course.objects.count(), 1)

    def test_database_rejects_case_and_whitespace_variants_on_bulk_insert_and_update(self):
        for code in ('csc102', 'CSC 102', 'CSC\t102'):
            with self.subTest(code=code), self.assertRaises(IntegrityError), transaction.atomic():
                Course.objects.bulk_create([Course(code=code, title='Duplicate', department='Computing')])
        other = Course.objects.create(code='CSC201', title='Programming', department='Computing')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Course.objects.filter(pk=other.pk).update(code='csc 102')

    def test_edit_keeps_course_id_and_timetable_links_and_resolves_pending_title(self):
        building = Building.objects.create(name='Computing building', campus_zone='Computing')
        room = Room.objects.create(name='Computing room', code='computing', building=building, room_type='Classroom',
                                   capacity=30, size_category='small')
        entry = TimetableDay.objects.create(room=room, course=self.course, date=date(2030, 1, 7), start_time=time(8), end_time=time(9))
        form = CourseAdminForm(instance=self.course, data={'code': ' csc 102 ', 'title': 'Verified title', 'department': 'Computing'})
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.pk, self.course.pk)
        entry.refresh_from_db()
        self.assertEqual(entry.course_id, saved.pk)
        pending = Course.objects.create(code='CSC202', title='', title_pending=True, department='Computing')
        pending.title = 'Confirmed title'
        pending.save(update_fields=['title'])
        pending.refresh_from_db()
        self.assertFalse(pending.title_pending)
