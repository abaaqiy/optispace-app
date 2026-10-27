"""Preview and apply date-specific timetable CSVs through the existing models."""
import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from rooms.models import Room
from scheduling.models import Course, TimetableDay

from .locking import lock_rooms


CSV_COLUMNS = (
    "id", "room", "course", "date", "start_time", "end_time",
    "academic_session", "cancelled",
)
REQUIRED_COLUMNS = set(CSV_COLUMNS) - {"id", "cancelled"}
MAX_FILE_BYTES = 1024 * 1024
MAX_ROWS = 1000
ENTRY_FIELDS = (
    "room_id", "course_id", "date", "start_time", "end_time",
    "academic_session", "is_cancelled",
)


class ImportProblem(Exception):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [errors]
        super().__init__("; ".join(self.errors))


@dataclass
class ImportRow:
    line: int
    values: dict
    room: Room
    course: Course
    requested_id: int | None = None
    existing: TimetableDay | None = None
    action: str = "Add"


@dataclass
class ImportPlan:
    rows: list[ImportRow]
    fingerprint: str

    @property
    def counts(self):
        return {action: sum(row.action == action for row in self.rows) for action in ("Add", "Update", "Unchanged")}


def decode_upload(upload):
    if upload.size > MAX_FILE_BYTES:
        raise ImportProblem("The CSV must be 1 MB or smaller. Split larger timetables into several files.")
    raw = upload.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ImportProblem("The CSV must be 1 MB or smaller.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImportProblem("Save the spreadsheet as CSV UTF-8, then upload it again.") from error


def parse_csv(text):
    if len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ImportProblem("The CSV must be 1 MB or smaller.")
    if "\x00" in text:
        raise ImportProblem("This file contains invalid characters. Save it as CSV UTF-8.")
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    errors, rows = [], []
    try:
        header = next(reader, None)
        if not header:
            raise ImportProblem("The file is empty. Download the CSV template to see the required columns.")
        header = [value.strip().lower() for value in header]
        if len(set(header)) != len(header):
            raise ImportProblem("Each column heading must appear only once.")
        missing, unknown = REQUIRED_COLUMNS - set(header), set(header) - set(CSV_COLUMNS)
        if missing:
            errors.append("Missing columns: " + ", ".join(sorted(missing)) + ".")
        if unknown:
            errors.append("Unknown columns: " + ", ".join(sorted(unknown)) + ". Use the downloadable template.")
        if errors:
            raise ImportProblem(errors)
        record_count = 0
        for cells in reader:
            if not any(value.strip() for value in cells):
                continue
            record_count += 1
            if record_count > MAX_ROWS:
                raise ImportProblem(f"Import up to {MAX_ROWS} classes at a time. Split this file into smaller files.")
            if len(cells) != len(header):
                errors.append(f"Row {reader.line_num}: expected {len(header)} columns; found {len(cells)}.")
                continue
            rows.append((reader.line_num, dict(zip(header, (value.strip() for value in cells)))))
    except csv.Error as error:
        raise ImportProblem(f"Row {reader.line_num}: invalid CSV formatting. Check commas and quotation marks.") from error
    if errors:
        raise ImportProblem(errors)
    if not rows:
        raise ImportProblem("The CSV has headings but no classes. Add at least one row.")
    return rows


def _find_reference(value, lookup, label):
    # Export prefixes spreadsheet formula characters with an apostrophe. Try the
    # literal name first so legitimate names starting with apostrophes still work.
    matches = lookup.get(value.casefold(), [])
    if not matches and value.startswith("'"):
        matches = lookup.get(value[1:].casefold(), [])
    if len(matches) != 1:
        if matches:
            raise ValueError(f'{label} "{value}" matches multiple records. Use a unique room code or correct duplicate course codes.')
        raise ValueError(f'{label} "{value}" was not found. Add it first or use the downloadable reference list.')
    return matches[0]


def resolve_rows(parsed):
    room_lookup, course_lookup = defaultdict(list), defaultdict(list)
    for room in Room.objects.select_related("building"):
        for key in {room.name.casefold(), room.code.casefold()}:
            room_lookup[key].append(room)
    for course in Course.objects.all():
        course_lookup[course.code.casefold()].append(course)
    errors, rows = [], []
    seen_ids = set()
    for line, data in parsed:
        try:
            room = _find_reference(data["room"], room_lookup, "Room")
            course = _find_reference(data["course"], course_lookup, "Course")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["date"]):
                raise ValueError("Use YYYY-MM-DD for the date.")
            selected_date = date.fromisoformat(data["date"])
            clocks = []
            for name in ("start_time", "end_time"):
                if not re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", data[name]):
                    raise ValueError(f"Use HH:MM or HH:MM:SS for {name}, in Lagos time.")
                clocks.append(time.fromisoformat(data[name]))
            if clocks[0] >= clocks[1]:
                raise ValueError("End time must be after start time on the same date.")
            session = data["academic_session"]
            if not session or len(session) > 30:
                raise ValueError("Academic session is required and must contain at most 30 characters.")
            cancelled = data.get("cancelled", "").casefold()
            if cancelled not in {"", "false", "no", "0", "true", "yes", "1"}:
                raise ValueError("Cancelled must be true or false (yes/no and 1/0 are also accepted).")
            identity = data.get("id", "")
            if identity and (not identity.isascii() or not identity.isdigit() or len(identity) > 18 or int(identity) < 1):
                raise ValueError("ID must be a positive number from an exported timetable, or blank for a new class.")
            identity = int(identity) if identity else None
            if identity in seen_ids:
                raise ValueError(f"Timetable ID {identity} occurs more than once in the file.")
            if identity:
                seen_ids.add(identity)
            rows.append(ImportRow(line=line, room=room, course=course, requested_id=identity, values={
                "room_id": room.pk, "course_id": course.pk, "date": selected_date,
                "start_time": clocks[0], "end_time": clocks[1], "academic_session": session,
                "is_cancelled": cancelled in {"true", "yes", "1"},
            }))
        except ValueError as error:
            errors.append(f"Row {line}: {error}")
    if errors:
        raise ImportProblem(errors)
    return rows


def entry_values(entry):
    return {name: getattr(entry, name) for name in ENTRY_FIELDS}


def _identity(values):
    return tuple(values[name] for name in ENTRY_FIELDS if name != "is_cancelled")


def _snapshot(rows, existing, reservations):
    payload = {
        "existing": [{"id": entry.pk, **entry_values(entry)} for entry in existing],
        "reservations": [(item.pk, item.room_id, item.date, item.start_time, item.end_time) for item in reservations],
        "rows": [{"line": row.line, "values": row.values, "id": row.existing.pk if row.existing else None,
                  "action": row.action, "room": (row.room.code, row.room.name),
                  "course": (row.course.code, row.course.title)} for row in rows],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def build_plan(rows, *, lock_entries=False):
    requested = {row.requested_id for row in rows if row.requested_id}
    queryset = TimetableDay.objects.select_for_update() if lock_entries else TimetableDay.objects.all()
    originals = queryset.order_by("pk").in_bulk(requested)
    missing = requested - originals.keys()
    if missing:
        raise ImportProblem("These timetable IDs no longer exist: " + ", ".join(map(str, sorted(missing))) + ". Export the timetable again.")
    room_ids = {row.room.pk for row in rows} | {obj.room_id for obj in originals.values()}
    dates = {row.values["date"] for row in rows} | {obj.date for obj in originals.values()}
    existing = list(queryset.filter(room_id__in=room_ids, date__in=dates).order_by("pk"))
    from bookings.models import Reservation
    reservations = list(Reservation.objects.filter(
        room_id__in=room_ids, date__in=dates, status=Reservation.Status.APPROVED,
        is_archived=False,
    ).order_by("pk"))
    identities = defaultdict(list)
    for obj in existing:
        identities[_identity(entry_values(obj))].append(obj)
    seen_rows, used_ids, errors = {}, set(), []
    for row in rows:
        key = _identity(row.values)
        if key in seen_rows:
            errors.append(f"Row {row.line}: duplicates the class in row {seen_rows[key]}. Keep one row per class.")
        seen_rows[key] = row.line
        if row.requested_id:
            row.existing = originals[row.requested_id]
            row.action = "Unchanged" if row.values == entry_values(row.existing) else "Update"
        else:
            matches = identities[key]
            if len(matches) > 1:
                errors.append(f"Row {row.line}: matches multiple saved classes. Export the timetable and specify an ID.")
            elif matches:
                row.existing = matches[0]
                if entry_values(row.existing) == row.values:
                    row.action = "Unchanged"
                else:
                    errors.append(f"Row {row.line}: this class has a different cancellation status in the database. Export it and keep its ID to change that status explicitly.")
        if row.existing:
            if row.existing.pk in used_ids:
                errors.append(f"Row {row.line}: timetable ID {row.existing.pk} is already included in another row.")
            used_ids.add(row.existing.pk)

    final_slots = defaultdict(list)
    for reservation in reservations:
        final_slots[(reservation.room_id, reservation.date)].append(
            (reservation.start_time, reservation.end_time, "an approved reservation")
        )
    for obj in existing:
        if obj.pk not in used_ids and not obj.is_cancelled:
            final_slots[(obj.room_id, obj.date)].append((obj.start_time, obj.end_time, f"saved timetable #{obj.pk}"))
    for row in rows:
        if row.values["is_cancelled"]:
            continue
        start, end = row.values["start_time"], row.values["end_time"]
        slots = final_slots[(row.room.pk, row.values["date"])]
        for other_start, other_end, label in slots:
            if start < other_end and end > other_start:
                errors.append(f"Row {row.line}: {row.room.name} overlaps {label} ({other_start:%H:%M}–{other_end:%H:%M}).")
        slots.append((start, end, f"row {row.line}"))
    if errors:
        raise ImportProblem(errors)
    return ImportPlan(rows=rows, fingerprint=_snapshot(rows, existing, reservations))


def preview_import(text):
    return build_plan(resolve_rows(parse_csv(text)))


def apply_import(text, expected_fingerprint, log_entry):
    rows = resolve_rows(parse_csv(text))
    requested_ids = {row.requested_id for row in rows if row.requested_id}
    original_rooms = set(TimetableDay.objects.filter(pk__in=requested_ids).values_list("room_id", flat=True))
    room_ids = {row.room.pk for row in rows} | original_rooms
    try:
        with lock_rooms(room_ids):
            # Re-resolve under the lock. A class might have been moved to another
            # room after the preview or before we acquired the original locks.
            rows = resolve_rows(parse_csv(text))
            current_rooms = set(TimetableDay.objects.filter(pk__in=requested_ids).values_list("room_id", flat=True))
            if not (current_rooms | {row.room.pk for row in rows}) <= room_ids:
                raise ImportProblem("A room assignment changed. Upload the CSV again to review current records.")
            # Row locks also protect against admin deletions, which do not use
            # the room locks used by saves. A deleted entry must not be recreated
            # by an import working from an earlier snapshot.
            plan = build_plan(rows, lock_entries=True)
            if plan.fingerprint != expected_fingerprint:
                raise ImportProblem("The timetable or approved reservations changed after this preview. Upload the CSV again to review the latest records.")
            # Clear only the old occupied periods being updated, inside this
            # transaction. This allows time swaps and cancel+replacement imports.
            # Other readers see the complete result only after commit.
            changed_ids = [row.existing.pk for row in rows if row.action == "Update"]
            TimetableDay.objects.filter(pk__in=changed_ids).update(is_cancelled=True)
            for row in rows:
                if row.action == "Unchanged":
                    continue
                entry = row.existing or TimetableDay()
                for name, value in row.values.items():
                    setattr(entry, name, value)
                entry.save()
                log_entry(entry, row.action)
            return plan.counts
    except ValidationError as error:
        raise ImportProblem(error.messages) from error
    except IntegrityError as error:
        raise ImportProblem("A referenced record changed during the import. Nothing was imported; upload the CSV again.") from error


def spreadsheet_cell(value):
    """Keep exported text from being interpreted as a spreadsheet formula."""
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")) else text
