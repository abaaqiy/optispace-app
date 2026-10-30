# Milestone 2: reservations

Students and lecturers request rooms; administrators review requests. Approved
reservations determine room availability alongside the school timetable.

## Using it

1. Students open **Reading Rooms**; lecturers use **Find a Room** or their dashboard.
2. Open room details and choose **Request this room**. Enter purpose, date, start
   and end times in Africa/Lagos time. Students can request small rooms; lecturers
   can request small or large rooms. Requests must start in the future and end
   later on the same day.
3. **My Reservations** shows the request as Pending. Administrators see pending
   requests on their dashboard and can Approve or Reject with an optional note.
   Django admin also offers these actions under **Reservations**.
4. Approval checks the current timetable and approved bookings again. If the slot
   now conflicts, the request stays Pending and an error explains the conflict.
5. The owner or an administrator can Cancel a pending or approved reservation
   until its end time, including while it is ongoing. Cancellation releases the
   slot while retaining its review and cancellation history.

Details cannot be edited after submission; cancel and submit a new request.
Rejected/cancelled requests cannot be revived. Completed reservations remain in
history and cannot be cancelled; expired pending requests can be rejected.
Administrators review requests rather than submitting them through the API.

## Availability and overlaps

Pending/rejected/cancelled requests do not hold a room. Different users may request
an overlapping pending slot; only one overlapping request can be approved. Repeated
overlapping pending requests by the same user for the same room are rejected.
Slots include their start and exclude their end, so 10:00–11:00 and 11:00–12:00
can both be approved. Separate rooms may be used simultaneously.

An approved booking makes **any room type Reserved during its exact interval**.
An active timetable class makes the room **Occupied**. The former 15-minute hall
warning is removed: before a booking begins, the existing class or gap determines
status. The countdown shows **Reservation ends in**, not time until it starts.
At the booking's end, the next class, booking or gap determines status. Cancellation
also recalculates availability immediately. No manual status change or background
worker is needed.

If the school timetable exists for the date, unoccupied gaps are Available. If it
has no entries for that date, gaps remain Unknown even when a booking is approved.
The app permits requests on such dates; administrators must verify timetable
completeness before approval. The app does not detect physical occupancy.

Room availability refreshes immediately after a reservation action on the current
page. Other open pages check every five seconds plus network time. Public room
schedules display only **Approved reservation**, never the purpose, requester or
review note. The campus class schedule continues to list classes only.

Timetable edits/restorations, CSV imports and reviewed image imports reject
approved booking conflicts. Imports and approvals share PostgreSQL room locks,
including simultaneous writes. A changed import preview must be reviewed again.

## API and access

All reservation endpoints require an active session. Mutations require CSRF.
Students/lecturers see only their own history; administrators (`is_superuser`)
see all current workflow records. Ordinary staff cannot approve/reject.

- `GET /api/reservations/?status=pending` (status optional).
- `POST /api/reservations/` with `roomId` (room code), `date` (`YYYY-MM-DD`),
  `startTime`/`endTime` (`HH:MM`), `purpose` (at most 200 characters).
- `POST /api/reservations/<reference>/approve/` or `reject/`, optionally with
  `note` (at most 500 characters).
- `POST /api/reservations/<reference>/cancel/`.

Account and status fields cannot be supplied when requesting. Invalid submissions
return 400; conflicting review/cancellation actions return 409. Other users'
references return 404. Approval, rejection and cancellation by administrators
also write Django admin History entries in the same transaction.

## Migration and local testing

`bookings.0002_archive_retired_reservations` preserves all pre-existing reservations
as archived history. This prevents retired bookings from unexpectedly blocking
rooms after restoration. Archived rows are viewable in Django admin, immutable,
and excluded from current requests, conflict checks and room availability.

Use the existing isolated development database, never the hosted `.env` database:

```sh
export DATABASE_URL='postgresql://optispace_local@127.0.0.1:55439/optispace_document_dev?sslmode=disable'
venv/bin/python backend/manage.py migrate
venv/bin/python backend/manage.py test bookings rooms scheduling accounts config
npm run lint
npm run build
node --test src/availability.test.js
sh scripts/run-document-dev.sh
```

See [isolated PostgreSQL and OCR setup](timetable-import.md) if the local database
has not been initialized. The local app is at `http://127.0.0.1:8001/`, with the
administrator login at `/staff-login`. The script applies migrations only to this
isolated local database and explains an occupied port. To use another port:
`OPTISPACE_DEV_PORT=8002 sh scripts/run-document-dev.sh`. Stop the local server
before restarting it to load backend changes; the script disables automatic reload.

### Verification

Backend tests cover simultaneous approvals,
approval versus timetable save/import, archival migration, access control and
cancellation, all room types, exact booking/class boundaries, and Unknown gaps.
Frontend tests cover reservation end countdowns and transitions between classes,
bookings and free periods. Browser checks cover requests, admin review, conflict
messages, private history, automatic availability updates and mobile layouts.
Local demo account instructions are in `.document-dev.local/reservation-testing.md`
on the development machine; that file is ignored by Git.
