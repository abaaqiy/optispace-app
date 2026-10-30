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
CSV imports require each date as a separate row. The **Import Image**
workflow described below can expand reviewed weekly entries into actual dates.

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
room locks, shared with reservation requests and approvals. CSV and reviewed
image imports both check approved bookings before saving. A conflict or save failure rolls back the whole import and its history
entries. No new database tables, migrations or background workers are required.
CSV uploads are processed in memory; they are not added to the
repository or saved as files on the server.

## Lecture timetable image import

Administrators can choose **Timetables → Import Image** to upload a PNG or JPEG
lecture timetable, up to 10 MB / 20 megapixels. PDF uploads and examination
layouts are not supported. **CSV import, export, templates and reference downloads
remain available**, including dated lectures and bulk corrections.

1. Upload one clear image with its weekday/time headings. Automatic layout
   detection supports Law-style stacked course/venue cells, Administration-style
   course/room cells and Chemistry-style Course/Venue columns. You can select the
   matching layout when automatic detection cannot read a heading.
2. Resolve repeated course and room names once. A selection fills every unresolved
   row with that exact detected name. Only existing catalogue records can be used;
   add missing records in a new tab and select **Refresh course and room choices**.
3. Use **Check shared headings once** to confirm or correct each weekday and time.
   Each change updates the entries linked to that original heading. A reader
   disagreement leaves the heading unresolved instead of silently choosing it.
4. Open **Review clear entries by day** and compare its compact course/room/time
   list with the image. One acknowledgement marks the eligible group reviewed.
   Uncertain text and incomplete entries remain in **Needs correction** for
   individual review. The editor shows 25 entries at a time, with search and filters.
5. **Show source** highlights the original cell and shows an enlarged crop. The
   image also has a zoom slider and a full-size view. Correct, duplicate or skip
   entries; add any missing ones. Editing clears the row's review tick.
6. Enter the academic session, first and last teaching dates, and optional excluded
   holiday dates. Confirm that you checked the complete image for omitted entries.
7. **Validate reviewed entries** expands the weekly rows into dated lectures.
   **Apply import** saves the checked entries together. Conflicts with classes or
   approved bookings, stale previews, missing references and invalid times block
   the entire save. Existing classes/cancellations are preserved.

Reviews are not automatic timetable publication. A recognition score is a review
aid, not proof that text is correct. At most 300 draft rows and 1,000 expanded
classes are allowed per import; use shorter teaching periods for larger schedules.

### OCR and hosting

Image processing uses OpenCV/Pillow to detect table cells and straighten small
rotations. The compact **PP-OCRv5 English recognition model** runs locally through
**ONNX Runtime** on cropped text lines. Tesseract independently rereads headings.
Course/room text stays within its original cell. Separate sections in a Chemistry
image can share weekday headings only when their column layout matches; review
calls this out. Unreadable values stay unresolved.

All processing is local to the app server. No uploaded timetable is sent to an
external OCR service and no paid API is used. The model is downloaded during setup
or the Docker build, pinned to SHA-256
`c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8`.
See [OCR model source and licence](ocr-model.md).

The six supplied images include one duplicated Law timetable and one exam image.
Local extraction of the Law example improved from 140 draft fragments with 32
incomplete rows to 130 course/venue pairs with no missing day/time/venue fields.
This measures field completeness, **not a claim of 100% OCR accuracy**. The small,
compressed Administration and split Chemistry images still need substantial
correction; use larger original images when available. The split Chemistry layout
now produces drafts rather than an empty result. Exam images are rejected.

One image is processed at a time per web process; additional attempts receive a
retry message. Processing time and working-image size are capped. The model uses
one CPU thread and one line per inference for the existing Free service. The
final local benchmark of the supplied images peaked at approximately 337 MB
for the OCR process. A separate Gunicorn test, including a 20-megapixel upload,
peaked at approximately 345 MB of proportional memory across the web server and
OCR processes. These are local measurements, not a guarantee for every upload.

Sources and drafts are stored in a private temporary cache accessible only to the
uploading administrator with a signed token. **Save draft** extends the two-hour
review period. Bookmark **Resume saved draft** after saving. Cache eviction or a
server restart can remove drafts; importing deletes the temporary review. Saved
classes remain in PostgreSQL. No schema migration is required.

### Local installation and testing

```sh
venv/bin/python -m pip install -r requirements.txt
sudo apt-get install tesseract-ocr tesseract-ocr-eng
venv/bin/python scripts/install-image-model.py
```

`OPTISPACE_IMAGE_MODEL` can point to the installed English ONNX file.
`TESSERACT_CMD` and `TESSDATA_PREFIX` support a non-system Tesseract installation.
The Dockerfile installs the same pinned model and dependencies for production.

The existing isolated local PostgreSQL cluster is at `.document-dev.local/pg`,
bound to `127.0.0.1:55439`, database `optispace_document_dev`:

```sh
sh scripts/run-document-dev.sh
```

Open `http://127.0.0.1:8001/admin/scheduling/timetableday/import-document/`.
If that port is occupied, use `OPTISPACE_DEV_PORT=8002 sh scripts/run-document-dev.sh`.
The launcher sets the local database explicitly and never changes `backend/.env`.
It installs the recognition model locally if missing. `OPTISPACE_PG_BIN` selects
the PostgreSQL binaries. The private local login is `.document-dev.local/login.txt`.

`backend/scheduling/fixtures/document_import/weekly.png` is a synthetic test image,
not an official OAU schedule. The user's original images are not committed.

Run tests only with an explicit isolated database URL:

```sh
DATABASE_URL='postgresql://optispace_local@127.0.0.1:55439/optispace_document_dev?sslmode=disable' \
  DJANGO_DEBUG=true \
  OPTISPACE_IMAGE_MODEL="$PWD/.document-dev.local/ocr-models/english.onnx" \
  venv/bin/python backend/manage.py test accounts bookings rooms scheduling config --noinput
```

The image tests cover field alignment, uncertain codes, merged headings,
continuations, PDF/exam rejection, actual image recognition when the model is
installed, explicit review, date expansion, conflicts, signatures, permissions,
CSRF and saved drafts. CSV tests retain the shared transaction/rollback coverage.

## Verification

```sh
DATABASE_URL='postgresql://LOCAL_USER@127.0.0.1:55439/LOCAL_DATABASE?sslmode=disable' \
  DJANGO_DEBUG=true venv/bin/python backend/manage.py test scheduling.test_timetable_import
```

The tests cover validation, duplicates, cancellation/restoration, time swaps,
conflicts after preview, rollback, filtered exports, permissions, CSRF, preview
expiry and spreadsheet/text handling. Browser checks also cover dark/light mode,
mobile layout and automatic frontend updates after an imported cancellation.
