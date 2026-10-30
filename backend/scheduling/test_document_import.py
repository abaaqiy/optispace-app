import json
import os
import shutil
import time
from datetime import date
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from rooms.models import Building, Room

from .document_admin import DOCUMENT_TTL
from .models import Course, TimetableDay
from .services.document_extract import (
    Cell,
    clock_range,
    day_value,
    extract_document,
    parse_table,
)
from .services.document_review import prepare_rows, references, suggest
from .services.timetable_import import ImportProblem


def grid(*rows):
    return [
        [
            Cell(text, (c * 100, r * 30, (c + 1) * 100, (r + 1) * 30))
            for c, text in enumerate(row)
        ]
        for r, row in enumerate(rows)
    ]


class TableAlignmentTests(SimpleTestCase):
    def fixture(self, name):
        path = Path(__file__).parent / "fixtures" / "document_import" / name
        return SimpleUploadedFile(name, path.read_bytes())

    def test_pdf_upload_is_rejected_before_ocr(self):
        with self.assertRaisesMessage(
            ImportProblem, "PDF uploads are no longer supported"
        ):
            extract_document(SimpleUploadedFile("timetable.pdf", b"%PDF-1.7 test"))

    @skipUnless(
        Path(os.environ.get("OPTISPACE_IMAGE_MODEL", "/missing")).is_file()
        and shutil.which(os.environ.get("TESSERACT_CMD", "tesseract")),
        "Install the image model and Tesseract for OCR integration tests.",
    )
    def test_real_image_keeps_cells_aligned(self):
        rows = extract_document(self.fixture("weekly.png"))["rows"]
        self.assertEqual(
            [
                (r["course_text"], r["room_text"], r["day"], r["start_time"])
                for r in rows
            ],
            [
                ("CHM102", "CH 102", "Monday", "08:00"),
                ("ICH204", "CH 220", "Tuesday", "08:00"),
                ("CHM402", "CH 110", "Monday", "09:00"),
                ("CHM102", "1000SLT", "Tuesday", "09:00"),
            ],
        )

    def test_exam_layout_is_rejected(self):
        with self.assertRaisesMessage(ImportProblem, "dated/examination layout"):
            parse_table(
                grid(
                    ("DATE", "COURSE", "VENUE", "TIME"),
                    ("7 July 2025", "DSS 310", "CH 102", "4-7 PM"),
                )
            )

    def test_weekday_columns_and_multiple_entries_keep_course_room_time_aligned(self):
        table = grid(
            ("", "Monday", "", "Tuesday", ""),
            ("TIME", "COURSE", "VENUE", "COURSE", "VENUE"),
            ("8-9", "CHM 102", "1000SLT", "ICH 204", "CH 220"),
            ("", "CHM 202", "FBLT", "", ""),
            ("9-10", "CHM 402", "CH 102", "CHM 102", "1000SLT"),
            ("unreadable", "CHM 305", "CH 110", "", ""),
        )
        rows, _, _ = parse_table(table)
        self.assertEqual(
            [
                (r["course_text"], r["room_text"], r["day"], r["start_time"])
                for r in rows
            ],
            [
                ("CHM102", "1000SLT", "Monday", "08:00"),
                ("ICH204", "CH 220", "Tuesday", "08:00"),
                ("CHM202", "FBLT", "Monday", "08:00"),
                ("CHM402", "CH 102", "Monday", "09:00"),
                ("CHM102", "1000SLT", "Tuesday", "09:00"),
                ("CHM305", "CH 110", "Monday", ""),
            ],
        )

    def test_law_stacked_cells_cannot_shift_pairs_after_unreadable_course(self):
        rows, _, _ = parse_table(
            grid(
                ("DAY/TIME", "8-9", "9-10", "10-11", "unreadable"),
                (
                    "Monday",
                    "PUL 101\nNEW MOOT\nCOURT",
                    "BUL S03\nLAW 204\nPUL 401\nLAW 203",
                    "JPL 201\nNEW MOOT\nCOURT",
                    "PUL 501\nLAW 206",
                ),
            )
        )
        found = [r for r in rows if r["course_text"] == "PUL401"]
        self.assertEqual(len(found), 1)
        self.assertEqual(
            (found[0]["room_text"], found[0]["day"], found[0]["start_time"]),
            ("LAW 203", "Monday", "09:00"),
        )
        uncertain = next(r for r in rows if r["course_text"] == "BULS03")
        self.assertEqual(uncertain["room_text"], "LAW 204")
        self.assertTrue(uncertain["note"])
        self.assertEqual(rows[-1]["start_time"], "")
        self.assertEqual(rows[0]["room_text"], "NEW MOOT COURT")

    def test_lgs_level_rows_use_day_and_own_time_column(self):
        table = grid(
            ("DAY", "CLASS", "8am-9am", "9am-10am", "10am-11am"),
            ("Monday", "B.Sc I", "LGS 101/Rm2", "LGS 203 Rm4", ""),
            ("", "B.Sc II", "", "LGS 305/Rm3", ""),
        )
        table[2][0] = table[1][0]
        rows, _, _ = parse_table(table)
        self.assertEqual(
            [
                (r["course_text"], r["room_text"], r["day"], r["start_time"])
                for r in rows
            ],
            [
                ("LGS101", "Rm2", "Monday", "08:00"),
                ("LGS203", "Rm4", "Monday", "09:00"),
                ("LGS305", "Rm3", "Monday", "09:00"),
            ],
        )

    def test_no_venue_is_borrowed_from_next_course(self):
        rows, _, _ = parse_table(
            grid(
                ("DAY", "8-9", "9-10", "10-11"),
                ("Tuesday", "PUL 101\nJPL 201\nLAW 204", "", ""),
            )
        )
        self.assertEqual(
            [(r["course_text"], r["room_text"]) for r in rows],
            [("PUL101", ""), ("JPL201", "LAW 204")],
        )

    def test_explicit_time_ranges(self):
        for text, expected in [
            ("8-9", ("08:00", "09:00")),
            ("12-1", ("12:00", "13:00")),
            ("1-2", ("13:00", "14:00")),
            ("11am-12pm", ("11:00", "12:00")),
            ("11-1 PM", ("11:00", "13:00")),
            ("4-7 PM", ("16:00", "19:00")),
            ("14:15-16:30", ("14:15", "16:30")),
            ("00:00-01:00", ("00:00", "01:00")),
            ("01:00-02:00", ("01:00", "02:00")),
            ("108-109", ("", "")),
            ("8-9 / 10-11", ("", "")),
            ("8AM", ("", "")),
            ("25-26", ("", "")),
            ("10:70-11:80", ("", "")),
        ]:
            with self.subTest(text=text):
                self.assertEqual(clock_range(text), expected)

    def test_continuation_keeps_same_weekday_columns_only_with_matching_width(self):
        _, _, context = parse_table(
            grid(
                ("", "Monday", "", "Tuesday", ""),
                ("TIME", "COURSE", "VENUE", "COURSE", "VENUE"),
            )
        )
        section = grid(("2-3", "CHM 102", "CH 102", "ICH 202", "ALT C"))
        for cell in section[0]:
            x0, y0, x1, y1 = cell.box
            cell.box = (x0, y0 + 200, x1, y1 + 200)
        rows, notes, _ = parse_table(section, continuation=context)
        self.assertEqual(
            [(r["day"], r["start_time"]) for r in rows],
            [("Monday", "14:00"), ("Tuesday", "14:00")],
        )
        self.assertIn("continuation", notes[0])
        self.assertEqual(
            parse_table(grid(("2-3", "CHM 102", "CH 102")), continuation=context)[0], []
        )
        self.assertEqual(parse_table(section, page=2, continuation=context)[0], [])
        for cell in section[0]:
            x0, y0, x1, y1 = cell.box
            cell.box = (x0 + 30, y0, x1 + 30, y1)
        self.assertEqual(parse_table(section, continuation=context)[0], [])

    def test_ambiguous_day_and_blurry_weekday_grid_are_not_mistaken_for_day_column(
        self,
    ):
        self.assertEqual(day_value("Monday / Tuesday"), "")
        table = grid(
            ("", "Monday", "Monday", "DRIDAY", "DRIDAY"),
            ("TIME", "coUESI", "VENUE", "COUKN", "VENUE"),
            ("8-9", "CHM102", "CH102", "ICH204", "CH220"),
        )
        rows, _, _ = parse_table(table)
        self.assertEqual(
            [(r["course_text"], r["day"]) for r in rows],
            [("CHM102", "Monday"), ("ICH204", "")],
        )
        unknown = grid(
            ("", "MONDAY", "MONDAY", "TweopsY", "TweopsY"), ("", "", "", "", "")
        )
        self.assertEqual(parse_table(unknown)[0], [])

    def test_blank_but_unreadable_time_does_not_inherit_previous_hour(self):
        table = grid(
            ("", "Monday", "", "Tuesday", ""),
            ("TIME", "COURSE", "VENUE", "COURSE", "VENUE"),
            ("8-9", "CHM102", "CH102", "", ""),
            ("", "CHM202", "CH102", "", ""),
            ("", "CHM302", "CH102", "", ""),
            ("", "CHM402", "CH102", "", ""),
        )
        table[4][0].has_content = True
        rows, _, _ = parse_table(table)
        self.assertEqual([r["start_time"] for r in rows], ["08:00", "08:00", "", ""])
        self.assertEqual(rows[0]["time_group"], rows[1]["time_group"])
        self.assertNotEqual(rows[1]["time_group"], rows[2]["time_group"])
        self.assertEqual(rows[2]["time_group"], rows[3]["time_group"])

    def test_continued_section_never_inherits_a_time_from_previous_section(self):
        _, _, context = parse_table(
            grid(
                ("", "Monday", "", "Tuesday", ""),
                ("TIME", "COURSE", "VENUE", "COURSE", "VENUE"),
                ("8-9", "CHM102", "CH102", "", ""),
            )
        )
        section = grid(("", "CHM202", "CH102", "", ""))
        for cell in section[0]:
            x0, y0, x1, y1 = cell.box
            cell.box = (x0, y0 + 200, x1, y1 + 200)
        rows, _, _ = parse_table(section, continuation=context)
        self.assertEqual((rows[0]["day"], rows[0]["start_time"]), ("Monday", ""))

    def test_pairs_keep_their_own_confidence_and_share_only_correct_headings(self):
        table = grid(
            ("DAY", "8-9", "9-10"),
            ("Monday", "PUL101\nLAW201\nBULS03\nLAW204", "JPL201\nLAW203"),
        )
        table[1][1].words = [
            {
                "text": text,
                "confidence": score,
                "x0": 100,
                "x1": 200,
                "top": 30 + i * 4,
                "bottom": 34 + i * 4,
            }
            for i, (text, score) in enumerate(
                zip(table[1][1].text.splitlines(), [99, 98, 45, 97])
            )
        ]
        rows, _, _ = parse_table(table)
        self.assertEqual([r["confidence"] for r in rows[:2]], [98, 45])
        self.assertEqual(rows[0]["day_group"], rows[2]["day_group"])
        self.assertEqual(rows[0]["time_group"], rows[1]["time_group"])
        self.assertNotEqual(rows[0]["time_group"], rows[2]["time_group"])
        self.assertEqual(rows[0]["source"], "PUL101\nLAW201")

    def test_inline_course_and_venue_without_separator(self):
        table = grid(("DAY", "CLASS", "8am-9am"), ("Monday", "BSc III", "LGS301SRm4"))
        rows, _, _ = parse_table(table)
        self.assertEqual(
            (rows[0]["course_text"], rows[0]["room_text"]), ("LGS301", "SRm4")
        )

    def test_concurrent_extractions_are_rejected_and_slot_released_after_errors(self):
        from .services import document_extract

        document_extract._extract_slots.acquire()
        try:
            with self.assertRaisesMessage(ImportProblem, "Another timetable image"):
                extract_document(SimpleUploadedFile("weekly.png", b"data"))
        finally:
            document_extract._extract_slots.release()
        for _ in range(2):
            with self.assertRaisesMessage(
                ImportProblem, "PDF uploads are no longer supported"
            ):
                extract_document(SimpleUploadedFile("weekly.pdf", b"%PDF-bad"))

    def test_invalid_and_oversized_uploads_are_rejected(self):
        with self.assertRaises(ImportProblem):
            extract_document(SimpleUploadedFile("bad.pdf", b"not a PDF"))
        with self.assertRaisesMessage(ImportProblem, "10 MB"):
            extract_document(
                SimpleUploadedFile("big.png", b"x" * (10 * 1024 * 1024 + 1))
            )

    def test_unknown_room_abbreviations_are_not_fuzzy_assigned(self):
        choices = [
            {"value": "one", "keys": ["1000slt"]},
            {"value": "two", "keys": ["ch102"]},
        ]
        self.assertEqual(suggest("CH 102", choices), "two")
        self.assertEqual(suggest("CH 103", choices), "")
        self.assertEqual(
            suggest("CH 102", choices + [{"value": "other", "keys": ["ch102"]}]), ""
        )


class DocumentWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="document-admin",
            email="document@oauife.edu.ng",
            password="Document-tests-482!",
        )
        building = Building.objects.create(
            name="Chemistry", campus_zone="Faculty of Science"
        )
        cls.room = Room.objects.create(
            name="Chemistry CH 102",
            code="ch102",
            building=building,
            capacity=80,
            room_type="Classroom",
            size_category="large",
        )
        cls.hall = Room.objects.create(
            name="Seminar hall",
            code="hall",
            building=building,
            capacity=40,
            room_type="Seminar Hall",
            size_category="small",
        )
        cls.course = Course.objects.create(
            code="CHM102", title="Chemistry", department="Chemistry"
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("admin:scheduling_timetableday_document")
        self.options = {
            "mode": "weekly",
            "academic_session": "2029/2030",
            "first_date": "2030-01-07",
            "last_date": "2030-01-21",
            "exclude_dates": "2030-01-14",
        }
        self.row = {
            "course": "CHM102",
            "room": "ch102",
            "day": "Monday",
            "date": "",
            "start_time": "08:00",
            "end_time": "09:00",
            "reviewed": True,
            "skip": False,
        }
        self.document = {
            "rows": [
                {
                    "course_text": "CHM 102",
                    "room_text": "CH102",
                    **self.row,
                    "source": "CHM 102 | CH 102",
                    "page": 1,
                    "box": [10, 10, 100, 40],
                }
            ],
            "pages": [{"image": b"jpeg", "width": 200, "height": 300}],
            "notices": ["Verify entries."],
        }

    def upload(self):
        with patch(
            "scheduling.document_admin.extract_document", return_value=self.document
        ):
            return self.client.post(
                self.url,
                {
                    "action": "extract",
                    "document": SimpleUploadedFile("example.jpg", b"example"),
                },
            )

    def review(self, token, rows=None, **options):
        return self.client.post(
            self.url,
            {
                "action": "review",
                "document_token": token,
                "rows": json.dumps(rows if rows is not None else [self.row]),
                **self.options,
                "coverage_checked": "yes",
                **options,
            },
        )

    def confirm(self, response):
        return self.client.post(
            self.url,
            {
                "action": "confirm",
                "document_token": response.context["document_token"],
                "preview": response.context["preview_token"],
            },
        )

    def test_full_workflow_expands_dates_excludes_holiday_and_updates_availability(
        self,
    ):
        upload = self.upload()
        self.assertContains(upload, "Review extracted entries")
        self.assertFalse(upload.context["rows"][0]["reviewed"])
        self.assertFalse(TimetableDay.objects.exists())
        preview = self.review(upload.context["document_token"])
        self.assertEqual(
            [r.values["date"] for r in preview.context["plan"].rows],
            [date(2030, 1, 7), date(2030, 1, 21)],
        )
        self.assertFalse(TimetableDay.objects.exists())
        self.assertEqual(self.confirm(preview).status_code, 302)
        self.assertEqual(TimetableDay.objects.count(), 2)
        self.assertEqual(LogEntry.objects.count(), 2)
        self.assertEqual(
            self.client.get(
                "/api/rooms/ch102/", {"date": "2030-01-07", "time": "08:30"}
            ).json()["status"],
            "occupied",
        )
        self.assertEqual(
            self.client.get(
                "/api/rooms/ch102/", {"date": "2030-01-07", "time": "09:00"}
            ).json()["status"],
            "available",
        )
        self.assertContains(self.confirm(preview), "expired or is invalid")

    def test_image_review_is_always_weekly_and_requires_coverage_confirmation(self):
        token = self.upload().context["document_token"]
        response = self.review(token, mode="dated")
        self.assertEqual(response.context["options"]["mode"], "weekly")
        blocked = self.review(token, coverage_checked="")
        self.assertContains(blocked, "Check the full image")
        self.assertFalse(blocked.context["preview_token"])
        self.assertFalse(TimetableDay.objects.exists())

    def test_unreviewed_incomplete_and_duplicate_entries_cannot_save(self):
        token = self.upload().context["document_token"]
        for rows, message in [
            ([{**self.row, "reviewed": False}], "tick Reviewed"),
            ([{**self.row, "room": ""}], "select an existing course and room"),
            ([{**self.row, "end_time": ""}], "both start and end"),
            ([self.row, self.row], "duplicates"),
            ([{**self.row, "skip": True}], "No classes remain"),
        ]:
            with self.subTest(message=message):
                response = self.review(token, rows)
                self.assertContains(response, message)
                self.assertFalse(response.context["preview_token"])
                self.assertFalse(TimetableDay.objects.exists())

    def test_preview_tampering_stale_and_expired_review(self):
        token = self.upload().context["document_token"]
        preview = self.review(token)
        response = self.client.post(
            self.url,
            {
                "action": "confirm",
                "document_token": token,
                "preview": preview.context["preview_token"] + "bad",
            },
        )
        self.assertContains(response, "invalid or expired")
        TimetableDay.objects.create(
            room=self.room,
            course=self.course,
            date=date(2030, 1, 7),
            start_time="08:15",
            end_time="09:00",
            academic_session="2029/2030",
        )
        self.assertContains(self.confirm(preview), "overlaps saved timetable")
        self.assertEqual(TimetableDay.objects.count(), 1)
        with patch(
            "django.core.signing.time.time", return_value=time.time() + DOCUMENT_TTL + 1
        ):
            self.assertContains(self.review(token), "expired or is invalid")

    def test_older_validation_cannot_be_applied_after_new_review(self):
        token = self.upload().context["document_token"]
        old = self.review(token)
        new = self.review(token, [{**self.row, "end_time": "08:45"}])
        self.assertContains(self.confirm(old), "invalid or expired")
        self.assertFalse(TimetableDay.objects.exists())
        self.assertEqual(self.confirm(new).status_code, 302)
        self.assertTrue(
            all(
                entry.end_time.strftime("%H:%M") == "08:45"
                for entry in TimetableDay.objects.all()
            )
        )

    def test_import_and_source_pages_require_permission_and_own_review(self):
        token = self.upload().context["document_token"]
        page_url = reverse("admin:scheduling_timetableday_document_page", args=[1])
        self.assertEqual(self.client.get(page_url, {"token": token}).status_code, 200)
        other = get_user_model().objects.create_superuser(
            username="other",
            email="other-doc@oauife.edu.ng",
            password="Other-tests-842!",
        )
        self.client.force_login(other)
        self.assertContains(self.review(token), "expired or is invalid")
        self.assertEqual(self.client.get(page_url, {"token": token}).status_code, 404)
        staff = get_user_model().objects.create_user(
            username="staff-doc",
            email="staff-doc@oauife.edu.ng",
            role="lecturer",
            is_staff=True,
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(page_url, {"token": token}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(self.url, {"action": "review"}).status_code, 403)

    def test_reference_aliases_and_no_automatic_fuzzy_matching(self):
        self.room.name = "Chemistry lecture room (CH 102)"
        self.room.save()
        refs = references()
        draft = prepare_rows([{"course_text": "CHM 102", "room_text": "CH 102"}], refs)[
            0
        ]
        self.assertEqual((draft["course"], draft["room"]), ("CHM102", "ch102"))
        self.assertFalse(draft["reviewed"])

    def test_missing_mappings_identify_the_fields_and_keep_review_edits(self):
        token = self.upload().context["document_token"]
        rows = [
            {
                **self.row,
                "course": "",
                "room": "",
                "course_text": "LAW 301",
                "room_text": "NEW MOOT COURT",
                "end_time": "10:00",
            }
        ]
        response = self.review(token, rows)
        self.assertContains(response, "course: LAW 301")
        self.assertContains(response, "room: NEW MOOT COURT")
        self.assertContains(response, "Refresh course and room choices")
        self.assertEqual(response.context["rows"], rows)
        self.assertFalse(TimetableDay.objects.exists())

    def test_refresh_matches_new_catalogue_records_without_saving_classes(self):
        token = self.upload().context["document_token"]
        rows = [
            {
                **self.row,
                "course": "",
                "room": "",
                "course_text": "LAW 301",
                "room_text": "NEW MOOT COURT",
                "reviewed": True,
            }
        ]
        self.review(token, rows)
        course = Course.objects.create(code="LAW301", title="Law", department="Law")
        room = Room.objects.create(
            code="moot",
            name="NEW MOOT COURT",
            building=self.room.building,
            capacity=40,
            room_type="Classroom",
            size_category="large",
        )
        response = self.client.post(
            self.url,
            {
                "action": "refresh",
                "document_token": token,
                "rows": json.dumps(rows),
                **self.options,
            },
        )
        refreshed = response.context["rows"][0]
        self.assertEqual(
            (refreshed["course"], refreshed["room"]), (course.code, room.code)
        )
        self.assertFalse(refreshed["reviewed"])
        self.assertFalse(response.context["preview_token"])
        self.assertFalse(TimetableDay.objects.exists())
        preview = self.review(
            response.context["document_token"], [{**refreshed, "reviewed": True}]
        )
        self.assertEqual(self.confirm(preview).status_code, 302)
        self.assertTrue(
            all(
                entry.room_id == room.pk and entry.course_id == course.pk
                for entry in TimetableDay.objects.all()
            )
        )

    def test_saved_draft_renews_token_and_invalidates_old_preview(self):
        token = self.upload().context["document_token"]
        previous = self.review(token)
        changed = [{**self.row, "course": "", "reviewed": False}]
        with patch(
            "django.core.signing.time.time",
            return_value=time.time() + DOCUMENT_TTL - 10,
        ):
            saved = self.client.post(
                self.url,
                {
                    "action": "save",
                    "document_token": token,
                    "rows": json.dumps(changed),
                    **self.options,
                },
            )
        self.assertEqual(saved.context["rows"], changed)
        self.assertFalse(saved.context["preview_token"])
        self.assertContains(self.confirm(previous), "invalid or expired")
        with patch(
            "django.core.signing.time.time",
            return_value=time.time() + DOCUMENT_TTL + 10,
        ):
            response = self.review(saved.context["document_token"])
        self.assertTrue(response.context["preview_token"])
        self.assertFalse(TimetableDay.objects.exists())

    def test_refresh_preserves_manual_selection_and_unknown_names_stay_blank(self):
        token = self.upload().context["document_token"]
        rows = [
            {**self.row, "course_text": "unknown", "room_text": "unknown"},
            {
                **self.row,
                "course": "",
                "room": "",
                "course_text": "CHM103",
                "room_text": "CH103",
                "reviewed": False,
            },
        ]
        response = self.client.post(
            self.url,
            {
                "action": "refresh",
                "document_token": token,
                "rows": json.dumps(rows),
                **self.options,
            },
        )
        self.assertEqual(response.context["rows"][0], rows[0])
        self.assertEqual(
            (
                response.context["rows"][1]["course"],
                response.context["rows"][1]["room"],
            ),
            ("", ""),
        )
        self.assertFalse(TimetableDay.objects.exists())

    def test_resume_restores_saved_rows_and_options_only_for_the_owner(self):
        token = self.upload().context["document_token"]
        rows = [{**self.row, "end_time": "10:00", "reviewed": False}]
        saved = self.client.post(
            self.url,
            {
                "action": "save",
                "document_token": token,
                "rows": json.dumps(rows),
                **self.options,
            },
        )
        token = saved.context["document_token"]
        resumed = self.client.get(self.url, {"review": token})
        self.assertEqual(resumed.context["rows"], rows)
        self.assertEqual(resumed.context["options"], self.options)
        self.assertFalse(resumed.context["preview_token"])
        other = get_user_model().objects.create_superuser(
            username="resume-other",
            email="resume-other@oauife.edu.ng",
            password="Resume-test-948!",
        )
        self.client.force_login(other)
        forbidden = self.client.get(self.url, {"review": token})
        self.assertContains(forbidden, "expired or is invalid")
        self.assertIsNone(forbidden.context["document"])
        self.assertFalse(TimetableDay.objects.exists())

    def test_invalid_json_and_review_values_return_errors(self):
        token = self.upload().context["document_token"]
        self.assertContains(
            self.client.post(
                self.url,
                {"action": "review", "document_token": token, "rows": "{broken"},
            ),
            "could not be read",
        )
        self.assertContains(
            self.review(token, [{**self.row, "room": ["bad"]}]), "invalid field value"
        )

    def test_teaching_period_and_expansion_limits(self):
        token = self.upload().context["document_token"]
        self.assertContains(
            self.review(token, last_date="2030-01-01"), "teaching period"
        )
        self.assertContains(
            self.review(token, last_date="2032-01-01"), "teaching period"
        )
        rows = [{**self.row, "start_time": "08:00"} for _ in range(25)]
        self.assertContains(
            self.review(token, rows, last_date="2031-01-07"), "more than 1000 classes"
        )
