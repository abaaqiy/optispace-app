# Optispace

Campus room availability and account management with a React/Vite frontend and
a Django REST API. Django stores accounts, sessions, rooms, facilities, and
timetables and reservations in PostgreSQL. There is no SQLite fallback.

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

Use `http://127.0.0.1:8000/admin/` to manage accounts, rooms, and published
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
Use the registered email address on the React login page; Django admin also accepts
the account's username. Both student and lecturer registration require matching
password and confirmation fields; the API requires `confirmPassword` and never
stores or returns it. A lecturer with a correct password but an inactive account
receives an administrator-activation message (HTTP 403). Incorrect credentials
continue to receive the generic invalid-email-or-password message (HTTP 401).

## First milestone: rooms and published availability

1. Sign into Django admin and add facilities and, optionally, an OAU building with
   its campus zone. Enter verified campus information; no sample rooms are inserted
   into the live database automatically.
2. Add a room using the searchable **Room name** dropdown (50 documented OAU
   suggestions plus **Others** for a custom name). The permanent internal code is
   generated automatically. Select its room type, capacity, size category and
   facilities. Choose a zone from 16 searchable faculty and college areas, or leave it blank
   to inherit the selected building's zone. A room's selected zone takes precedence.
   See [catalogue sources and editing behaviour](docs/room-catalog.md).
3. Optionally add courses with their code, title, and department.
4. Add a timetable day for the room and date. Its coverage start/end must describe
   the period for which you have verified the full schedule. Leave it unpublished
   until the lecture allocations have been entered and checked.
5. Add lecture allocations within that coverage, optionally linking each to a course
   and academic session. Overlapping lectures are rejected. Publish the timetable day.
6. In the frontend, open Lecture Rooms (large rooms) or Reading Rooms (small rooms).
   Search by zone, minimum capacity, facilities, status, or a specific date/time.
   Open Details to see the full published timetable. Class Schedule lists the
   published, active lectures for its selected date.

Dates and times use `Africa/Lagos`. The room page refreshes every minute, when the
browser regains focus, or when Refresh rooms is clicked. “Occupied soon” is currently
free but has a lecture starting within an hour; it is included in the Available filter.
No published timetable, or a time outside its coverage, gives Unknown. Availability
is derived from the timetable and does not detect unscheduled physical occupancy.

The existing screen layouts and room response fields are preserved. Buildings and
course links are optional, so existing room and schedule records remain valid.
Reservations now use the workflow described below. The public campus class schedule
continues to list published lecture allocations; private reservation purposes are
shown only to their requester and administrators.

### API routes

| Method and route | Purpose |
| --- | --- |
| `GET /api/rooms/` | Room list; filters: `date` + `time`, `zone`, `building`, `capacity`, `category`, `status`, repeated `facilities` |
| `GET /api/rooms/<code>/` | Room details and availability for `date` + `time` (or now) |
| `GET /api/rooms/filters/` | Saved campus zones/buildings and supported facilities |
| `GET /api/schedules/?date=YYYY-MM-DD` | Published, non-cancelled lectures; defaults to today in Lagos |

Room list responses stay arrays with `id`, `name`, `zone`, `type`, `capacity`,
`sizeCategory`, `facilities`, `status`, `statusText`, `currentSchedule`,
`nextSchedule`, `hourlySchedule`, and `availabilityAt`. `building` and `roomNumber`
are additive. Catalog and timetable writes use Django admin; public API routes are read-only.

## Second milestone: reservation requests and approval

1. An administrator publishes a room's timetable for the requested date, including
   its verified coverage hours and lecture allocations. An empty published day
   means that its coverage hours have no scheduled lectures.
2. A student opens **Reading Rooms** to request a small room. An activated lecturer
   can request either a small or large room from **Find a Room** or the dashboard.
   Use **Book** or **Reserve Room**, enter a purpose, date, start and end, and submit.
3. Requests appear as **Pending** in **My Reading Bookings** / **My Schedule**.
   Pending requests do not block the room. Administrators see requests under
   **Booking Approvals**, with status filtering and optional review notes.
4. Approval checks availability again and marks that period **Reserved**. A rejected
   request keeps its history and review note. The requester or an administrator can
   cancel a pending or approved reservation before its start time; cancelling an
   approved reservation releases its time immediately.

All dates and times use `Africa/Lagos`. Reservations are for one day, must start in
the future, and must fit inside a published timetable's coverage hours. They cannot
overlap an active lecture or approved reservation. Different users can request the
same free period while approval is pending; only one overlapping request can be
approved. A user's duplicate/overlapping pending request for the same room is rejected.
Requests cannot be edited; cancel and submit a new one to change their details.

The server assigns the owner, reference and status. Only active superuser
administrators can approve or reject requests. Students/lecturers can list only
their own reservations. Session authentication and CSRF protection apply to writes.
Public room responses show a generic **Reserved** label without the requester's
name or purpose. Approved reservations stay visible even if a timetable is later
unpublished; other periods then have Unknown availability.

Room row locks serialize approvals and lecture saves, including edits and restoring
cancelled lectures. Both directions check for conflicts inside a transaction.
Use the application/admin save paths; direct SQL, `QuerySet.update()` and bulk writes
bypass this validation. Reservation records retain who reviewed/cancelled them and
when. Django admin offers the same guarded actions through **Manage Reservations**;
direct reservation editing, adding and deletion are disabled there.

| Method and route | Purpose |
| --- | --- |
| `GET /api/reservations/` | Own requests, or all for administrators; optional `status` filter |
| `POST /api/reservations/` | Request using `roomId` (room code), `date`, `startTime`, `endTime`, `purpose` |
| `POST /api/reservations/<reference>/approve/` | Administrator approval; optional `note` |
| `POST /api/reservations/<reference>/reject/` | Administrator rejection; optional `note` |
| `POST /api/reservations/<reference>/cancel/` | Requester or administrator cancellation |

Use `YYYY-MM-DD` and `HH:MM`. Invalid requests return 400; unauthorized actions
return 403, and other users' references return 404. A review/cancellation that is
no longer valid returns 409 with a message. Lists refresh every minute, on window
focus, and via **Refresh reservations**. Room filters include **Reserved**, and
room details include approved reservation slots alongside lectures and free gaps.

Apply the new schema with `python backend/manage.py migrate`. The migration adds
the reservation table and preserves existing accounts, rooms and timetables.

Focused verification (from `backend/`):

```sh
../venv/bin/python manage.py test bookings scheduling rooms
```

The tests cover role access, CSRF, validation, approval/rejection/cancellation,
availability boundaries, privacy, Django admin actions and simultaneous writes.

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
