# Milestone 3: school timetable import and export

Milestone 3 adds spreadsheet import/export to the existing **Timetables** admin
page. The two scheduling categories remain **Courses** and **Timetables**. Manual
editing, cancellations and student/lecturer dashboards use the same timetable
records and API responses. Active classes show Occupied during their interval;
approved reservations show Reserved. Imported classes do not trigger an early
Reserved warning, for any room type.

## Import a school timetable

1. Open **Import School Timetable** in the administrator dashboard, or
   **Manage Timetables → Import CSV**.
2. Download the **CSV template**, **room names and codes**, and **course codes**.
   Create any missing rooms or courses before importing.
3. Fill in one row per class on a specific date in Excel, LibreOffice, or another
   spreadsheet application. Save the file as **CSV UTF-8**.
4. Upload it and choose **Preview CSV**. This step does not save classes.
5. Review the actions, rooms, courses, dates, times, sessions and cancellation
   statuses. Correct any reported row errors in the file, then upload it again.
6. Choose **Apply import** to save the reviewed entries together.

Room lists, open room details and campus schedules use the imported data on their
next automatic refresh, normally within five seconds plus network/request time.

## CSV columns

| Column | Value |
| --- | --- |
| `id` | Leave blank for a new class. Keep the exported ID when editing or cancelling an existing class. |
| `room` | A saved room name or permanent room code. Matching ignores case. Use the code when a name is ambiguous. |
| `course` | A saved course code. Matching ignores case; ambiguous codes must be corrected first. |
| `date` | Specific date in `YYYY-MM-DD` format. |
| `start_time` | Start time in `HH:MM` or `HH:MM:SS`, using Africa/Lagos time. |
| `end_time` | End time in the same format, after the start time on that date. |
| `academic_session` | Required text, for example `2026/2027`, up to 30 characters. |
| `cancelled` | `true` or `false`. Blank means false. `yes`/`no` and `1`/`0` are also accepted. |

The `id` and `cancelled` columns can be omitted when creating active classes. All
other column headings are required. Blank rows are ignored. Import at most
**1,000 classes and 1 MB per file**; split larger timetables into multiple files.

For example, if the listed room and course already exist:

```csv
id,room,course,date,start_time,end_time,academic_session,cancelled
,Geology Classroom F13,CSC201,2026-11-02,09:00,11:00,2026/2027,false
```

This is a format example, not an official OAU class allocation. Download the saved
reference lists to get the actual room names/codes and course codes in your database.
The importer does not read PDF timetables or automatically repeat weekly classes;
include each required date as a separate row.

## Update or cancel existing classes

Use filters or search in **Manage Timetables**, then choose **Export CSV**. The
download includes **all matching rows**, including rows on other result pages.
It includes saved timetable IDs and cancellation statuses.

Edit that file, retain each existing row's `id`, and use Preview CSV → Apply import.
You can change rooms, dates, times, courses, academic sessions or cancellation
statuses. Set `cancelled` to `true` to release a class's time slot, or `false` to
restore it. Restoring fails if another active class or approved reservation overlaps that room/time.
Legacy entries without a course or academic session must be completed before import.

- Uploading a class with identical room, course, date, times, session and status
  leaves it **Unchanged**. Re-uploading the same file does not create duplicates.
- Changing a saved cancellation status requires its explicit `id`. A new import
  cannot silently restore an existing cancelled class by matching its details.
- Rows omitted from an import are kept. Importing a file does not delete the
  rest of the school timetable.
- Duplicate rows, repeated IDs, missing references, invalid times and overlapping
  active classes or approved reservations are rejected. Adjacent slots are allowed.
- The complete resulting timetable is checked, allowing a time swap or a
  cancellation and replacement in one import.

## Validation and access

A preview expires after 30 minutes and belongs to the administrator who uploaded
it. The server verifies that the reviewed data is unchanged when Apply import is
submitted. If relevant timetable records or approved reservations changed after the preview, upload again
to review the current records.

Imports require both add and change permission for Timetables. Export requires
view permission. Ordinary student and lecturer accounts cannot import or export
through admin. Each created or updated class has an entry in Django admin History.

All changes in a file are saved in one PostgreSQL transaction under the affected
room locks, shared with reservation requests and approvals. Imports check approved
bookings before saving. A conflict or save failure rolls back the whole import
and its history entries. CSV uploads are processed in memory; they are not added to the
repository or saved as files on the server.

## Verification

```sh
cd backend
../venv/bin/python manage.py test scheduling.test_timetable_import
```

The tests cover validation, duplicates, cancellation/restoration, time swaps,
conflicts after preview, rollback, filtered exports, permissions, CSRF, preview
expiry and spreadsheet/text handling. Browser checks also cover dark/light mode,
mobile layout and automatic frontend updates after an imported cancellation.
