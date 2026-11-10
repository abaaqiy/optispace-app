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
| `start_time` | Start time with AM/PM, such as `2:30 PM` or `2:30:15 PM`, using Africa/Lagos time. Existing `HH:MM` / `HH:MM:SS` files also work. |
| `end_time` | End time in the same format, after the start time on that date. |
| `academic_session` | Required text, for example `2026/2027`, up to 30 characters. |
| `cancelled` | `true` or `false`. Blank means false. `yes`/`no` and `1`/`0` are also accepted. |

The `id` and `cancelled` columns can be omitted when creating active classes. All
other column headings are required. Blank rows are ignored. Import at most
**1,000 classes and 1 MB per file**; split larger timetables into multiple files.

For example, if the listed room and course already exist:

```csv
id,room,course,date,start_time,end_time,academic_session,cancelled
,Geology Classroom F13,CSC201,2026-11-02,9:00 AM,11:00 AM,2026/2027,false
```

This is a format example, not an official OAU class allocation. Download the saved
reference lists to get the actual room names/codes and course codes in your database.
CSV exports use AM/PM and preserve seconds when present. Re-importing them does
not change the times. Midnight is **12:00 AM**; noon is **12:00 PM**. The timezone
remains Africa/Lagos. API time values and stored timestamps retain their existing
formats; clock labels, admin widgets, image-review inputs and dashboards use AM/PM.
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

1. Upload one clear image with its weekday/time headings. Detection supports
   Law-style stacked cells, Administration course/room cells, Chemistry Course/Venue
   columns, and Pharmacy Part II–V grids with times across the top.
2. **Confirm shared details**: faculty, department, session, semester and source
   version are suggested from the heading where readable. Enter the first/last
   teaching dates and optional excluded dates once. A faculty-wide timetable may
   have no department. Do not infer every course's department or a venue's building
   from the heading; shared university spaces can belong to other faculties.
3. Resolve unique course/venue labels once. Match existing records (including
   documented room aliases), or **prepare a new course/room here**. Codes/names are
   prefilled. Course-title suggestions match exact codes against sourced OAU
   handbooks/course pages, across departments. Each shows its edition and source;
   confirm the curriculum applies before selecting it. No title is guessed for
   unknown codes, and typed titles are never automatically replaced. Coverage is
   partial: see [course-title sources](course-title-sources.md). Historical Pharmacy
   sources are explicitly **not verified for PharmD**.
   When the code is clear but its title is unknown, select **I confirmed this
   course code in the image; its title is awaiting confirmation**. This stores
   the code and an empty title with an explicit pending flag; it never invents a
   title. Classes still affect availability. Later, use **Courses → Title awaiting
   confirmation → Yes**, open the course and enter the verified title. Saving a
   nonempty title clears the flag without changing its timetable links.
   Use **Inspect locations / correct reading / skip** to open each source cell,
   correct one reading or an entire group, or skip unwanted entries. Skipped rows
   require no reference records; unused proposals are not created. The Skipped
   filter restores them. Missing-reference groups come from OCR readings, not from
   handbook suggestions. A code absent from the current handbook is not necessarily
   invalid, especially when timetable and handbook sessions differ.
   Room names/types use the same searchable choices and Others custom entries as
   manual Room admin. The actual building and capacity still need confirmation.
   An authorised admin can prepare a new building inline using the same searchable
   teaching/study building catalogue and Others as manual Building admin, with its
   actual campus area. Facilities and room numbers are optional.
   Prepared records are editable drafts and are reused for repeated labels. Map
   different OCR spellings to the same saved or proposed record. No database rows
   are created at this stage. Save/resume retains the proposals.
4. Compare the **weekly preview** against the image, including missing cells. It
   keeps course, venue, day, time and Part/group together, flags incomplete entries
   and overlaps within the draft, and links to the editable row/source crop.
   Confirm clear entries together after comparison. Uncertain readings and
   grouped practicals still need individual attention. Shared-heading corrections,
   day groups, source zoom, search and the 25-row editor remain available.
5. Validate the reviewed entries. This checks proposed references and their
   permissions, expands dates, and detects duplicate classes and overlaps with
   saved timetables/approved reservations. Review the counts and new-record list.
6. **Confirm and import** saves new buildings/courses/rooms and all classes in one
   transaction. Any failed validation or save rolls back the whole import. An
   image-import lock serializes reference creation; room locks coordinate with
   bookings and CSV imports. Stale previews require validation again. Existing
   records and cancellations are not overwritten. Each new class retains shared
   image provenance (faculty, department, semester, version, dates and filename)
   shown on its edit page; no extra scheduling category is added.

The November restructure is local development work, not deployed. Migration
`scheduling.0006` adds optional import provenance and `scheduling.0007` adds the
explicit pending-title flag; apply them only to the explicitly configured local
database while testing. The CSV columns remain unchanged; exported clock times
now use AM/PM, and the importer accepts both formats.

Reviews are not automatic timetable publication. A recognition score is a review
aid, not proof that text is correct. At most 300 weekly draft rows and 16,000 expanded
classes are allowed per image import, so an ordinary full teaching period can be
imported together. CSV retains its independent 1,000-row limit.

The supplied Pharmacy 2024/2025 Rain image confirms B217 and provides a Part II–V
layout test. The reader keeps part labels separate from courses, reads horizontal
weekday labels in tall merged cells, and spans merged practical cells across their
time columns. Group letters such as (A), (B), or (G) are not assumed to be venues.
Grouped practical sessions without identifiable venues remain flagged for
correction/splitting or skipping. Chemistry's small image and Pharmacy's imperfect
print still produce OCR errors (for example B217 may read 3217); neither image is
claimed to import without review. Source photographs are not committed.

A second local OCR reader checks recognised course cells. Where complete codes
disagree it adds a warning, preserving the first reading and its source location
for inspection. Agreement is not proof of correctness. It uses no handbook-based
replacement rule and applies across departments. For the supplied Chemistry
2021/2022 Rain image, visual review confirmed **ICH205 on Tuesday 13:00–14:00 in
CH102**; **ICH302** was a misreading of **ICH102**, Thursday 15:00–16:00 in CH102
(the extracted time heading also needs correction). The current run did not
reproduce ICH408; the image shows **CHM408 on Wednesday 08:00–09:00 in CH220**.
The supplied Chemistry handbook lists ICH406 among requirements without a title
there, so its title remains unverified. These observations are test findings, not
department-specific automatic corrections.

Drafts expire seven hours after upload or their latest save/validation. Saving
renews both the signed link and cached image/review. Already expired or cleared
drafts cannot be recovered; re-upload those images. Existing unsaved drafts keep
their original cache expiry until saved under the new version.

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
October local benchmark of the supplied images peaked at approximately 337 MB
for the OCR process. A separate Gunicorn test, including a 20-megapixel upload,
peaked at approximately 345 MB of proportional memory across the web server and
OCR processes. These are local measurements, not a guarantee for every upload.

Sources and drafts are stored in a private temporary cache accessible only to the
uploading administrator with a signed token. **Save draft** extends the seven-hour
review period. Reopen **Timetables → Import Image → Your saved image drafts** and
select the filename. The list shows save/expiry times and only your own reviews;
expired, evicted and imported reviews disappear. You can also bookmark
**Resume saved draft** after saving. Older drafts created before this list was
introduced appear after saving them again with their original link. Temporary
storage cleanup or replacement can remove drafts. Importing deletes the temporary
review; saved classes and source metadata remain in PostgreSQL (migration 0006).

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

The JavaScript form tests run without a browser using the production review
template and jsdom (development dependency only):

```sh
node --test backend/scheduling/static/scheduling/*.test.js
```

They cover saving/resuming pending course titles, individual OCR corrections,
skipping/restoring proposals and building-name selections/custom entries. These
DOM tests do not replace a visual check of Select2 in light and dark mode.

## Verification

```sh
DATABASE_URL='postgresql://LOCAL_USER@127.0.0.1:55439/LOCAL_DATABASE?sslmode=disable' \
  DJANGO_DEBUG=true venv/bin/python backend/manage.py test scheduling.test_timetable_import
```

The tests cover validation, duplicates, cancellation/restoration, time swaps,
conflicts after preview, rollback, filtered exports, permissions, CSRF, preview
expiry and spreadsheet/text handling. Browser checks also cover dark/light mode,
mobile layout and automatic frontend updates after an imported cancellation.
