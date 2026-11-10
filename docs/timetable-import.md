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
2. **Confirm shared details**: faculty, department and source version are suggested
   from the heading where readable. Select the saved **Teaching semester**; the
   session, teaching dates and breaks come from its shared settings. An exact
   session/semester heading match suggests a saved semester, but never invents
   dates. A faculty-wide timetable may
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

### Shared semester settings

Open **Timetables → Semester settings → Add semester setting**. Save the academic
session, Harmattan/Rain semester, teaching start/end dates and optional holiday or
break dates once. All departments can then select the same semester during image
review. Settings use Django's normal administrator add/change/view/delete
permissions and remain inside Timetables rather than adding a scheduling category.

Weekly classes are generated only on their weekdays within those inclusive dates,
excluding configured holidays. No classes are generated after the teaching end
date. The image form has no first/last teaching-date inputs or per-image date
overrides. CSV and manual timetable entries remain date-specific.

Save a draft even when its semester has not yet been configured. After adding
settings in another tab, reopen the draft and choose the semester. Existing drafts
retain their edits; older drafts' dates do not override shared settings. Only an
exact session/semester match is suggested for older drafts.

Validation and confirmation read the current semester settings on the server.
Changing them invalidates a pending preview, which must be validated again.
Confirmed image imports retain a snapshot of the dates used and a link to the
selected semester. Editing settings affects subsequent imports; it does not
reschedule already imported classes. Adjust existing entries in Timetables when
needed. A semester linked to an import cannot be deleted. No university calendar
dates are seeded or inferred from an academic-session label.

The November restructure is local development work, not deployed. Migration
`scheduling.0006` adds optional import provenance, `scheduling.0007` adds the
explicit pending-title flag, `scheduling.0008` adds durable private image drafts,
`scheduling.0009` extends active drafts to 24 hours, and `scheduling.0010` adds
shared semester settings. Apply them only to the explicitly configured local
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

Drafts save quietly about one second after editing pauses, with a save at least
every five seconds during continuous editing when the connection is responsive.
Background saves send only review data, not the source image or handbook catalogue.
They preserve rows, shared details, selected semester, review/skip flags, proposed
records and unfinished course/room, heading and correction fields. Unfinished
forms still need their explicit Apply/Use/Update action before validation; autosave
never creates courses, rooms, buildings or timetable records.

The **Save draft** button remains. Successful autosaves show no pop-up or success
message. Failed saves show an inline warning and retry with a bounded delay; a
lost response is retried safely before later edits. Requests run one at a time.
Saving/validating manually waits for an in-flight autosave, then submits the
latest edits. A signed save version rejects stale tabs rather than overwriting
newer work. Reopen the saved draft to resolve a conflicting tab. Autosave does
not apply an import, and new edits invalidate any prior import preview.

Unsaved changes prompt before navigating away; a browser/PC crash before a save
completes can still lose the latest edits. There is no background keepalive while
idle. Searching, paging and viewing the image do not extend draft expiry.

Drafts expire 24 hours after upload or their latest changed autosave/manual save/validation. Saving
renews both the signed link and the database expiry. Reopening or refreshing a
draft list does not extend this expiry. Time while the computer is off counts
towards the 24 hours. Unsaved browser edits cannot be recovered after closing.
Legacy drafts cleared from the old temporary
cache cannot be recovered from the original image without reviewing it again.
Migration `scheduling.0009` extends existing unexpired drafts to 24 hours from
their last save. It preserves saved edits and does not restore expired drafts.

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

Source images and draft metadata are stored together in the configured PostgreSQL
database (`scheduling.0008`), with the uploading administrator and explicit
save/expiry timestamps. Images use a binary column; corrections, proposals,
headings and the selected semester use JSON. No cache, temporary file or in-memory index
is needed to reopen a saved draft. PC/app/database restarts do not remove it when
the same persistent database is used. Local development keeps these rows in the
isolated local PostgreSQL database, not hosted production.

For a one-time upgrade, stop the old app process, apply migration `0008`, then
run `python backend/manage.py migrate_legacy_image_drafts` with the same database,
signing key and operating-system user as the old app. This moves surviving,
unexpired temporary drafts into PostgreSQL, preserving their owner, saved edits
and original expiry. It retires the old cache copies only after committing the
database save. Restart the app afterward. Already cleared or expired temporary
drafts cannot be restored by this command.

Reopen **Timetables → Import Image → Your saved image drafts** and select the
filename. Only the owner's unexpired drafts are listed. The list generates fresh
signed links, including after a signing-key change; database expiry is still
enforced. Other admins cannot read the draft. Importing and removing its draft
are one database transaction, so a failed import preserves the review. Deleting
the owner also deletes their drafts. No new admin category is added.

Expired drafts and images are removed when drafts are listed or saved. There is
no size-based eviction of active drafts. For installations that need cleanup
even when no admin visits, run `python backend/manage.py cleanup_image_drafts`
periodically with the intended database configuration. Database backups should
be treated as private because they now include unexpired source images. No paid
storage service is needed.

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
