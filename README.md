# Optispace

Campus room availability and account management with a React/Vite frontend and
a Django REST API. Django stores accounts, sessions, rooms, facilities, and
timetables in PostgreSQL. There is no SQLite fallback.

## Backend setup

Use Python 3.12 or newer and run these commands from the repository root:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp backend/.env.example backend/.env
```

Set `DATABASE_URL` in `backend/.env` to your PostgreSQL service URI:

```dotenv
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST:PORT/defaultdb?sslmode=require
```

For the configured Aiven service, use database `defaultdb`, user `avnadmin`, port
`16541`, and host
`pg-3bc36c4b-olagundoyemiracle1234-3dfb.g.aivencloud.com`.
URL-encode special characters in the username or password. The local `.env` file
is ignored by Git; never put database credentials in frontend code or a `VITE_`
environment variable.

Django loads `backend/.env` regardless of the working directory. A process-level
`DATABASE_URL` takes precedence, so deployments can supply it through their secret
configuration. Missing or non-PostgreSQL URLs stop startup with a configuration
error. Connections require TLS by default, have a 10-second connection timeout,
and close at the end of each request. This prevents Django's threaded development
server from exhausting the hosted database's connection limit. For certificate verification,
use `sslmode=verify-full&sslrootcert=/absolute/path/to/ca.pem` with the Aiven CA.

Apply the schema and start the API:

```sh
python backend/manage.py migrate
python backend/manage.py createsuperuser
python backend/manage.py runserver 127.0.0.1:8000
```

Use `http://127.0.0.1:8000/admin/` to manage accounts, rooms, and
timetables. Lecturer accounts require administrator approval before sign-in.

## Frontend setup

In a separate terminal:

```sh
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Vite forwards `/api/`, `/admin/`, and `/static/`
requests to Django. The room screens and campus schedule now load saved records
from PostgreSQL. Login sessions survive a refresh, and logout ends the server session.
The public page offers student and lecturer login only. Administrators open
`http://127.0.0.1:5173/staff-login` directly; the application has no links to this
page. It also supports a trailing slash. Existing sessions and Django permissions
still control access. In production, serve the SPA for `/staff-login` as well as `/`.
Use the registered email address on the React login page; Django admin also accepts
the account's username. Both student and lecturer registration require matching
password and confirmation fields; the API requires `confirmPassword` and never
stores or returns it. A lecturer with a correct password but an inactive account
receives an administrator-activation message (HTTP 403). Incorrect credentials
continue to receive the generic invalid-email-or-password message (HTTP 401).

## First milestone: rooms and timetable availability

1. Sign into Django admin and add facilities and a building. **Building name** has
   38 researched OAU suggestions plus **Others** for a custom name, with search
   by name or nickname. Choose its campus area from the searchable dropdown.
   See [building sources and migration behaviour](docs/building-catalog.md).
   Suggestions do not insert database records automatically.
2. Add a room using the searchable **Room name** dropdown (50 documented OAU
   suggestions plus **Others** for a custom name). The permanent internal code is
   generated automatically. Select its room type, capacity, size category and
   facilities. A building is required; the room uses that building's campus area.
   There is no separate room-zone field to fill in.
   See [catalogue sources and editing behaviour](docs/room-catalog.md).
   To update a saved room, choose **Manage Rooms → Edit room** beside its row
   (the room name is plain text). Change any of the seven room-detail fields and
   choose **Save** at the top or bottom. The room's internal identifier stays
   the same, preserving its timetable and reservation links.
3. Under **Scheduling → Courses**, add the course code, title and department.
4. Under **Scheduling → Timetables**, fill in **Room**, **Date**, **Start time**,
   **End time**, **Course**, and **Academic session** (for example, `2026/2027`).
   One row represents one scheduled class. Save another timetable row for another
   class, including in the same room on the same date. All six fields are editable.
5. Save to apply the entry immediately. There is no Lectures section, separate
   lecture title, day-coverage form or publishing step.
   The course supplies the displayed class name. Overlapping active entries for the
   same room/date are rejected. Edit the times to reschedule. Select **Cancelled**
   and save to release a class's time slot while keeping its record. Clear Cancelled
   to restore the class, provided no replacement class overlaps it.
6. In the frontend, open Lecture Rooms (large rooms) or Reading Rooms (small rooms).
   Search by zone, minimum capacity, facilities, status, or a specific date/time.
   Open Details to see the full timetable. Class Schedule lists the
   saved classes for its selected date.

Dates and times use `Africa/Lagos`. Room lists, open details and campus schedules
check the API five seconds after each completed request, and on focus, returning
to a visible tab or reconnecting. This is polling, so a change normally appears
within five seconds plus network/request time; it is not an instantaneous push.
The Refresh rooms button fetches immediately, shows progress and the last successful
update time, and reports errors with a retry. Failed room requests clear stale
availability rather than continuing to display it. Status and countdowns advance
every second in the current-time view. A selected date/time is a fixed preview,
while the underlying timetable still refreshes.

Availability checks all stored classes for that room/date, regardless of user or
search filters. A date with no entries anywhere in the school timetable is Unknown.
When the school timetable has entries for that date, a room without an active class
at the selected time is Available (subject to the hall-only Reserved warning).
Cancelled rows are ignored for occupancy, but still establish that a timetable
exists for that date, so cancelling the only class releases the room. Another
active class in the same slot keeps the room Occupied. This assumes the saved
school timetable contains every relevant class for that date; the app cannot
infer classes that have not been entered.
Availability is derived from the timetable and does not detect unscheduled physical
occupancy. The automatic Reserved warning is described below.

The existing screen layouts and room response fields are preserved. Every room
requires a building; its public `zone` value and zone filtering come from that
building. New admin entries require a course and academic session. Legacy entries without
them remain visible as "Scheduled class" until an administrator fills them in.
Existing room IDs are retained; timetable rows supply the schedule references.
The public campus class schedule lists saved classes and marks cancelled entries
**Cancelled**. The lecturer overview tab is called **Dashboard**.
Students and lecturers can browse rooms and timetables; booking requests have been
removed.

### API routes

| Method and route | Purpose |
| --- | --- |
| `GET /api/rooms/` | Room list; filters: `date` + `time`, `zone`, `building`, `capacity`, `category`, `status`, repeated `facilities` |
| `GET /api/rooms/<code>/` | Room details and availability for `date` + `time` (or now) |
| `GET /api/rooms/filters/` | Saved campus zones/buildings and supported facilities |
| `GET /api/schedules/?date=YYYY-MM-DD` | Saved timetable classes; defaults to today in Lagos |

Room list responses stay arrays with `id`, `name`, `zone`, `type`, `capacity`,
`sizeCategory`, `facilities`, `status`, `statusText`, `currentSchedule`,
`nextSchedule`, `hourlySchedule`, and `availabilityAt`. `building` and `roomNumber`
are additive. Responses also include `reservedUntil`, `reservedSeconds` and
`statusTimeline` (timestamped status periods for the selected date). These let
the current-time view advance locally between refreshes, including in an open room
dialog and when filtering by status. Catalog and timetable writes use Django admin;
public API routes are read-only.

## Room status and hall-only Reserved warning

The room's **Room type** controls whether Reserved can appear. Only **Seminar Room**,
**Seminar Hall** and **Event Hall** have the 15-minute warning; the latter two are
now available in the admin dropdown. Lecture Theatre, Classroom, reading rooms,
laboratories, studios, meeting rooms and custom types never display Reserved.

Statuses use Lagos time and the school's saved timetable:

- **Occupied:** an active class covers this time. For lecture rooms this lasts
  until the class ends, including through back-to-back classes without a gap.
- **Available:** no active class covers this time, either because the class was
  cancelled or because no class is scheduled in that interval.
- **Reserved:** for eligible seminar/event spaces only, the next active session
  starts within 15 minutes. This warning takes priority even during a preceding
  session, whose name remains visible. Cancelled sessions never trigger it.
- **Unknown:** no school timetable has been entered for the selected date.

For a single active timetable entry from 10:00 to 12:00:

| Time on that date | Lecture room | Seminar/event hall |
| --- | --- | --- |
| Before 09:45 | Available | Available |
| 09:45–10:00 | Available | Reserved |
| 10:00–12:00 | Occupied | Occupied |
| After 12:00 | Available | Available |
| Class cancelled, with no replacement | Available | Available |

Intervals include their start and exclude their end. Saved cancellations and
restorations reach student and lecturer views through automatic polling, including
status filters and an open room dialog. The campus schedule retains cancelled
entries with their status. No scheduled job or manual room-status update is needed.
A future-date search stays at its chosen moment while reflecting timetable edits.

Booking forms, personal request pages, approvals and reservation API routes have
been removed for all roles. `/api/reservations/` and its former action URLs return
404. Historical reservation rows and migration history remain in PostgreSQL; they
are not exposed in Django admin and do not affect room status or lecture validation.
The booking removal requires no database migration. The retained `bookings` app only
keeps those existing records and migration dependencies intact.

Timetable saves lock the room and reject overlapping active entries, including when
restoring a cancelled class.
Use Django admin/model save paths: direct SQL and bulk updates bypass model
validation.

Focused verification:

```sh
cd backend
../venv/bin/python manage.py test bookings scheduling rooms
```

Frontend countdown verification (from the repository root):

```sh
node --test src/availability.test.js
```

These tests cover retired endpoints, archived record preservation, timetable editing, data migration, countdown boundaries, back-to-back lectures, status filtering, and room
editing without changing existing record links.

## Simplified scheduling upgrade

Scheduling has two admin categories: **Courses** and **Timetables**. Migration
`scheduling.0004_flatten_timetables` moves each active lecture into one timetable
row, copies its room, date, start/end, course and academic session, and removes the
Allocation model/table. The first class keeps its old parent timetable ID; any
additional classes get new timetable IDs. API response fields stay compatible.

Before upgrading, back up `scheduling_timetableday`, `scheduling_allocation`, and
`scheduling_course`, then run `python backend/manage.py migrate`. Removed lecture
fields (title and cancellation), cancelled records and empty day-coverage records
are retained only in that backup. The migration does not invent courses or turn
empty days into occupied periods. Restoring the old structure with records requires
restoring the backup. All current active classes retain their times and course links.

Migration `scheduling.0005_timetable_cancellation` adds **Cancelled** directly to
Timetables with a default of false. It preserves every existing record and does
not reintroduce the separate Lectures category. Apply with
`python backend/manage.py migrate` after backing up timetable records.

## Adding another administrator

An existing superuser can use **Manage Users → Add user**:

1. Enter a username, OAU staff email, password and confirmation. Choose Lecturer
   for the initial role so the `@oauife.edu.ng` email is valid, then save.
2. Open the new user. Under Permissions, enable **Active**, **Staff status** and
   **Superuser status**, then save. Superuser status makes the account an application
   administrator regardless of its initial student/lecturer role.
3. The new administrator signs in with their email at `/staff-login`, or their
   username at Django's `/admin/` page.

Staff status alone allows entry to Django admin with assigned permissions; it does
not make the account an application administrator. Public registration cannot grant
staff or superuser permissions.

## Required-building upgrade

Before updating an existing installation, back up room/building records including
old room-zone overrides. All existing rooms must already have a building; otherwise
migration `rooms.0003` stops and lists unassigned room codes. Assign their buildings
using the previous application version, then retry `python backend/manage.py migrate`.
The migration retains existing building links, makes them required and removes the
room-zone column. A building's campus area replaces any conflicting room override.
See [the migration notes](docs/building-catalog.md#upgrade).

## Verify the database

```sh
python backend/manage.py check
python backend/manage.py migrate --check
curl --fail http://127.0.0.1:8000/api/health/
```

The health endpoint executes `SELECT 1`. A working database returns HTTP 200:

```json
{"status":"ok","service":"Optispace API","database":"ok"}
```

A database connection failure returns HTTP 503 with `database: "unavailable"`
without exposing connection details.

Run the backend suite from the backend directory so Django discovers every test:

```sh
cd backend
../venv/bin/python manage.py test
```

Tests use a separate PostgreSQL database named `test_<configured database name>`.
The database role needs permission to create and drop that test database.
The configured Aiven service also has an empty `postgres` maintenance database
for Django's test runner. On another service without that database, create it
once with `CREATE DATABASE postgres;` while connected to the application database;
otherwise Django can fail when removing its temporary test database.
For CI, set `DATABASE_URL` to a dedicated PostgreSQL service. A local PostgreSQL
server without TLS can explicitly use `?sslmode=disable` for development tests.

## Existing SQLite installations

The checked local SQLite database contained no accounts, rooms, or timetable
records when this project switched to PostgreSQL. Django migrations recreate its
schema, content types, and permissions on PostgreSQL. The ignored local SQLite
file is retained as a backup and is no longer used by the application.

For another installation with existing SQLite records, stop application writes,
back up that database, and export its data using the old SQLite configuration
before switching. Apply migrations on PostgreSQL, then import the fixture with
`loaddata`, excluding generated content types and permissions from the export.
