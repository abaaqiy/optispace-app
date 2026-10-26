import csv
import io
import time as system_time
from datetime import date, time
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from rooms.models import Building, Room

from .import_admin import PREVIEW_MAX_AGE, PREVIEW_SALT
from .models import Course, TimetableDay
from .services.timetable_import import (
    CSV_COLUMNS, MAX_FILE_BYTES, MAX_ROWS, ImportProblem, apply_import,
    decode_upload, parse_csv, preview_import, spreadsheet_cell,
)


def timetable_csv(*rows, columns=CSV_COLUMNS):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class TimetableImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="import-admin", email="import-admin@oauife.edu.ng", password="Import-Tests-493!",
        )
        cls.building = Building.objects.create(name="Science building", campus_zone="Faculty of Science")
        cls.room = Room.objects.create(
            name="Science classroom", code="science-room", building=cls.building,
            room_type="Classroom", capacity=80, size_category="large",
        )
        cls.hall = Room.objects.create(
            name="Seminar Hall", code="seminar-hall", building=cls.building,
            room_type="Seminar Hall", capacity=40, size_category="small",
        )
        cls.course = Course.objects.create(code="CSC101", title="Computing", department="Computing")

    def setUp(self):
        self.client.force_login(self.admin)
        self.import_url = reverse("admin:scheduling_timetableday_import")

    def row(self, **extra):
        return {
            "id": "", "room": self.room.name, "course": self.course.code,
            "date": "2030-01-15", "start_time": "10:00", "end_time": "12:00",
            "academic_session": "2029/2030", "cancelled": "false", **extra,
        }

    def entry(self, **extra):
        return TimetableDay.objects.create(
            **{"room": self.room, "course": self.course, "date": date(2030, 1, 15),
               "start_time": time(10), "end_time": time(12), "academic_session": "2029/2030", **extra},
        )

    def upload(self, text):
        return self.client.post(self.import_url, {
            "action": "preview", "csv_file": SimpleUploadedFile("timetable.csv", text.encode(), "text/csv"),
        })

    def confirm(self, preview):
        return self.client.post(self.import_url, {"action": "confirm", "preview": preview})

    def apply(self, text):
        return apply_import(text, preview_import(text).fingerprint, lambda entry, action: None)

    def test_preview_has_no_writes_then_confirm_updates_existing_frontend_contract(self):
        response = self.upload(timetable_csv(self.row(), self.row(room=self.hall.code)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 to add; 0 to update; 0 unchanged.")
        self.assertFalse(TimetableDay.objects.exists())
        self.assertFalse(LogEntry.objects.exists())
        response = self.confirm(response.context["preview_token"])
        self.assertRedirects(response, reverse("admin:scheduling_timetableday_changelist"))
        self.assertEqual(TimetableDay.objects.count(), 2)
        self.assertEqual(LogEntry.objects.count(), 2)
        params = {"date": "2030-01-15", "time": "09:45"}
        rooms = {r["id"]: r for r in self.client.get("/api/rooms/", params).json()}
        self.assertEqual(rooms[self.room.code]["status"], "available")
        self.assertEqual(rooms[self.hall.code]["status"], "reserved")
        self.assertEqual(rooms[self.hall.code]["reservedSeconds"], 900)
        self.assertEqual(len(self.client.get("/api/schedules/", {"date": "2030-01-15"}).json()), 2)

    def test_identical_reupload_is_unchanged_and_does_not_restore_cancelled_classes(self):
        text = timetable_csv(self.row())
        self.apply(text)
        self.assertEqual(self.apply(text), {"Add": 0, "Update": 0, "Unchanged": 1})
        entry = TimetableDay.objects.get()
        entry.is_cancelled = True
        entry.save()
        with self.assertRaisesMessage(ImportProblem, "different cancellation status"):
            self.apply(text)
        entry.refresh_from_db()
        self.assertTrue(entry.is_cancelled)

    def test_explicit_id_can_cancel_only_class_and_restore_it(self):
        entry = self.entry()
        self.apply(timetable_csv(self.row(id=entry.pk, cancelled="true")))
        response = self.client.get("/api/rooms/science-room/", {"date": "2030-01-15", "time": "10:30"})
        self.assertEqual(response.json()["status"], "available")
        self.assertEqual(self.client.get("/api/schedules/", {"date": "2030-01-15"}).json()[0]["status"], "Cancelled")
        self.apply(timetable_csv(self.row(id=entry.pk)))
        self.assertEqual(self.client.get("/api/rooms/science-room/", {"date": "2030-01-15", "time": "10:30"}).json()["status"], "occupied")
        self.assertEqual(TimetableDay.objects.count(), 1)

    def test_time_swap_and_cancel_with_replacement_validate_final_state(self):
        first = self.entry()
        second = self.entry(start_time=time(12), end_time=time(14))
        self.apply(timetable_csv(
            self.row(id=first.pk, start_time="12:00", end_time="14:00"),
            self.row(id=second.pk, start_time="10:00", end_time="12:00"),
        ))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.start_time, time(12))
        self.assertEqual(second.start_time, time(10))
        replacement = Course.objects.create(code="CSC102", title="Replacement", department="Computing")
        self.apply(timetable_csv(
            self.row(id=second.pk, cancelled="true"), self.row(course=replacement.code),
        ))
        self.assertEqual(TimetableDay.objects.filter(is_cancelled=False).count(), 2)
        self.assertTrue(TimetableDay.objects.get(pk=second.pk).is_cancelled)

    def test_invalid_rows_conflicts_and_duplicate_ids_save_nothing(self):
        existing = self.entry(start_time=time(8), end_time=time(9))
        cases = [
            (timetable_csv(self.row(room="Missing room")), "was not found"),
            (timetable_csv(self.row(course="Missing course")), "was not found"),
            (timetable_csv(self.row(date="2030-02-30")), "Row 2:"),
            (timetable_csv(self.row(date="15/01/2030")), "YYYY-MM-DD"),
            (timetable_csv(self.row(start_time="25:00")), "Row 2:"),
            (timetable_csv(self.row(end_time="09:00")), "End time"),
            (timetable_csv(self.row(cancelled="maybe")), "true or false"),
            (timetable_csv(self.row(academic_session="")), "Academic session"),
            (timetable_csv(self.row(id="-1")), "positive number"),
            (timetable_csv(self.row(id=999999)), "no longer exist"),
            (timetable_csv(self.row(id=existing.pk), self.row(id=existing.pk, date="2030-01-16")), "more than once"),
            (timetable_csv(self.row(), self.row()), "duplicates"),
            (timetable_csv(self.row(), self.row(start_time="11:00", end_time="13:00")), "overlaps row 2"),
            (timetable_csv(self.row(start_time="08:30", end_time="10:00")), "overlaps saved timetable"),
        ]
        for text, message in cases:
            with self.subTest(message=message):
                response = self.upload(text)
                self.assertContains(response, message)
                self.assertIsNone(response.context["preview_token"])
                self.assertEqual(TimetableDay.objects.count(), 1)
                self.assertFalse(LogEntry.objects.exists())

    def test_cancelled_rows_do_not_block_active_imports_and_adjacent_slots_allowed(self):
        self.entry(is_cancelled=True)
        other = Course.objects.create(code="CSC102", title="Other", department="Computing")
        self.apply(timetable_csv(self.row(course=other.code), self.row(start_time="12:00", end_time="14:00")))
        self.assertEqual(TimetableDay.objects.filter(is_cancelled=False).count(), 2)

    def test_stale_or_replayed_preview_cannot_overwrite_later_changes(self):
        entry = self.entry()
        preview = self.upload(timetable_csv(self.row(id=entry.pk, cancelled="true"))).context["preview_token"]
        entry.end_time = time(13)
        entry.save()
        response = self.confirm(preview)
        self.assertContains(response, "changed after this preview")
        entry.refresh_from_db()
        self.assertFalse(entry.is_cancelled)
        self.assertEqual(entry.end_time, time(13))
        fresh = self.upload(timetable_csv(self.row(id=entry.pk, cancelled="true"))).context["preview_token"]
        self.assertEqual(self.confirm(fresh).status_code, 302)
        self.assertContains(self.confirm(fresh), "changed after this preview")
        self.assertEqual(LogEntry.objects.count(), 1)

    def test_new_conflict_after_preview_blocks_whole_import(self):
        text = timetable_csv(self.row(), self.row(room=self.hall.code))
        token = self.upload(text).context["preview_token"]
        self.entry(start_time=time(11), end_time=time(13))
        self.assertContains(self.confirm(token), "overlaps saved timetable")
        self.assertEqual(TimetableDay.objects.count(), 1)
        self.assertFalse(TimetableDay.objects.filter(room=self.hall).exists())

    def test_failed_save_rolls_back_prior_changes_and_admin_logs(self):
        entry = self.entry()
        token = self.upload(timetable_csv(self.row(id=entry.pk, cancelled="true"), self.row(room=self.hall.code))).context["preview_token"]
        original_save = TimetableDay.save

        def fail_hall(obj, *args, **kwargs):
            if obj.room_id == self.hall.pk:
                raise ValidationError("Concurrent timetable update")
            return original_save(obj, *args, **kwargs)

        with patch.object(TimetableDay, "save", fail_hall):
            self.assertContains(self.confirm(token), "Concurrent timetable update")
        entry.refresh_from_db()
        self.assertFalse(entry.is_cancelled)
        self.assertEqual(TimetableDay.objects.count(), 1)
        self.assertFalse(LogEntry.objects.exists())

    def test_preview_signature_expiry_and_user_binding(self):
        token = self.upload(timetable_csv(self.row())).context["preview_token"]
        self.assertContains(self.confirm(token + "tampered"), "expired or is invalid")
        with patch("django.core.signing.time.time", return_value=system_time.time() + PREVIEW_MAX_AGE + 60):
            self.assertContains(self.confirm(token), "expired or is invalid")
        other = get_user_model().objects.create_superuser(username="other-admin", email="other@oauife.edu.ng", password="Import-Tests-284!")
        self.client.force_login(other)
        self.assertContains(self.confirm(token), "expired or is invalid")
        self.assertFalse(TimetableDay.objects.exists())

    def test_permissions_and_csrf_apply_to_import_and_downloads(self):
        urls = [self.import_url, reverse("admin:scheduling_timetableday_template"), reverse("admin:scheduling_timetableday_references"), reverse("admin:scheduling_timetableday_export")]
        student = get_user_model().objects.create_user(username="reader", email="reader@student.oauife.edu.ng")
        staff = get_user_model().objects.create_user(username="staff", email="staff@oauife.edu.ng", role="lecturer", is_staff=True)
        for user in (student, staff):
            self.client.force_login(user)
            for url in urls:
                with self.subTest(user=user.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 302 if user == student else 403)
            self.assertEqual(self.client.post(self.import_url, {"action": "confirm", "preview": "x"}).status_code, 302 if user == student else 403)
        staff.user_permissions.add(Permission.objects.get(codename="view_timetableday"))
        self.client.force_login(staff)
        self.assertEqual(self.client.get(urls[-1]).status_code, 200)
        self.assertEqual(self.client.get(self.import_url).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(self.import_url, {"action": "confirm", "preview": "x"}).status_code, 403)

    def test_exports_include_filters_and_roundtrip_cancellations(self):
        active = self.entry()
        self.entry(room=self.hall, is_cancelled=True)
        response = self.client.get(reverse("admin:scheduling_timetableday_export"), {"is_cancelled__exact": "0"})
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], str(active.pk))
        self.assertEqual(rows[0]["room"], active.room.code)
        self.assertEqual(self.apply(response.content.decode("utf-8-sig"))["Unchanged"], 1)
        page = self.client.get(reverse("admin:scheduling_timetableday_changelist"), {"is_cancelled__exact": "0"})
        self.assertContains(page, "export/?is_cancelled__exact=0")
        self.assertContains(page, "Import CSV")
        self.assertContains(self.client.get(reverse("admin:scheduling_timetableday_references")), self.room.name)
        self.assertContains(self.client.get(reverse("admin:scheduling_timetableday_references"), {"kind": "courses"}), "CSC101")

    def test_csv_structure_encoding_and_limits(self):
        valid = timetable_csv(self.row())
        self.assertEqual(len(parse_csv("\ufeff" + valid)), 1)
        for text, message in (("", "empty"), ("room,room\na,b", "only once"), ("room,course\na,b", "Missing columns"),
                              (valid.replace("cancelled", "unexpected", 1), "Unknown columns"),
                              (valid + "bad,row\n", "expected 8 columns"), (valid.replace("Science classroom", "\x00"), "invalid characters")):
            with self.subTest(message=message), self.assertRaisesMessage(ImportProblem, message):
                parse_csv(text)
        with self.assertRaisesMessage(ImportProblem, "1 MB"):
            decode_upload(SimpleUploadedFile("large.csv", b"x" * (MAX_FILE_BYTES + 1)))
        with self.assertRaisesMessage(ImportProblem, "UTF-8"):
            decode_upload(SimpleUploadedFile("other.csv", b"\xff\xfe\x00"))
        with self.assertRaisesMessage(ImportProblem, "1 MB"):
            parse_csv("x" * (MAX_FILE_BYTES + 1))
        with self.assertRaisesMessage(ImportProblem, "1000 classes"):
            parse_csv(timetable_csv(*[self.row() for _ in range(MAX_ROWS + 1)]))

    def test_name_matching_is_case_insensitive_and_reports_ambiguity(self):
        self.apply(timetable_csv(self.row(room=self.room.name.upper(), course="csc101")))
        self.assertEqual(TimetableDay.objects.count(), 1)
        Course.objects.create(code="csc101", title="Ambiguous", department="Computing")
        with self.assertRaisesMessage(ImportProblem, "multiple records"):
            preview_import(timetable_csv(self.row(date="2030-01-16")))

    def test_preview_escapes_html_and_downloads_neutralise_formulas(self):
        self.course.title = "<script>alert(1)</script>"
        self.course.save()
        response = self.upload(timetable_csv(self.row()))
        self.assertNotContains(response, self.course.title)
        self.assertContains(response, "&lt;script&gt;")
        for value in ("=2+2", "+command", "-command", "@SUM(A1)", "\t=value"):
            self.assertTrue(spreadsheet_cell(value).startswith("'"))
        self.assertEqual(spreadsheet_cell("CSC101"), "CSC101")

    def test_signed_preview_contains_only_expected_user_and_rows(self):
        token = self.upload(timetable_csv(self.row())).context["preview_token"]
        value = signing.loads(token, salt=PREVIEW_SALT, max_age=PREVIEW_MAX_AGE)
        self.assertEqual(set(value), {"user", "csv", "fingerprint"})
        self.assertEqual(value["user"], self.admin.pk)
