"""Convert explicitly reviewed draft rows to the existing validated CSV plan."""

import csv
import io
import re
from datetime import date, timedelta

from rooms.models import Room
from scheduling.models import Course

from .document_extract import DAYS, MAX_DRAFT_ROWS
from .timetable_import import CSV_COLUMNS, MAX_ROWS, ImportProblem


def normalise(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def references():
    rooms = [
        {
            "value": r.code,
            "label": f"{r.name} — {r.building.name}",
            "keys": list(
                {
                    normalise(r.code),
                    normalise(r.name),
                    normalise(r.room_number),
                    *(normalise(p) for p in re.findall(r"\(([^)]+)\)", r.name)),
                }
            ),
        }
        for r in Room.objects.select_related("building").order_by("name")
    ]
    courses = [
        {"value": c.code, "label": f"{c.code} — {c.title}", "keys": [normalise(c.code)]}
        for c in Course.objects.order_by("code")
    ]
    return {"rooms": rooms, "courses": courses}


def suggest(value, choices):
    key = normalise(value)
    matches = [item["value"] for item in choices if key and key in item["keys"]]
    return matches[0] if len(matches) == 1 else ""


def prepare_rows(rows, refs):
    return [
        {
            **row,
            "course": suggest(row["course_text"], refs["courses"]),
            "room": suggest(row["room_text"], refs["rooms"]),
            "reviewed": False,
            "skip": False,
            "day_checked": False,
            "time_checked": False,
        }
        for row in rows
    ]


def refresh_rows(rows, refs):
    """Fill missing exact matches after an admin adds catalogue records."""
    valid = {
        key: {item["value"] for item in refs[key + "s"]} for key in ("course", "room")
    }
    result = []
    for original in rows:
        row = original.copy()
        if not row.get("skip"):
            for key in ("course", "room"):
                if not isinstance(row.get(key), str) or row.get(key) not in valid[key]:
                    value = suggest(row.get(key + "_text", ""), refs[key + "s"])
                    if value != row.get(key, ""):
                        row[key] = value
                        row["reviewed"] = False
        result.append(row)
    return result


def reviewed_csv(rows, options, *, refs=None):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_DRAFT_ROWS:
        raise ImportProblem(f"Review between 1 and {MAX_DRAFT_ROWS} rows at a time.")
    if options.get("mode") not in {"weekly", "dated"}:
        raise ImportProblem(
            "Choose a weekly lecture timetable or a timetable with specific dates."
        )
    session = options.get("academic_session", "").strip()
    if not session or len(session) > 30:
        raise ImportProblem("Enter the academic session (at most 30 characters).")
    excluded = set()
    try:
        for value in re.split(r"[\s,]+", options.get("exclude_dates", "").strip()):
            if value:
                excluded.add(date.fromisoformat(value))
        if options["mode"] == "weekly":
            first, last = (
                date.fromisoformat(options.get(key, ""))
                for key in ("first_date", "last_date")
            )
            if not 0 <= (last - first).days <= 370:
                raise ValueError
    except ValueError as error:
        raise ImportProblem(
            "Use valid YYYY-MM-DD dates. The teaching period must end after it starts and span at most 370 days."
        ) from error
    result, errors = [], []
    valid = (
        {key: {item["value"] for item in refs[key + "s"]} for key in ("course", "room")}
        if refs is not None
        else None
    )
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ImportProblem("The review data is invalid. Reload the document.")
        if row.get("skip") is True:
            continue
        if row.get("reviewed") is not True:
            errors.append(
                f"Review row {index}: check its course, room, day/date and time, then tick Reviewed."
            )
            continue
        if any(
            not isinstance(row.get(key, ""), str) or len(row.get(key, "")) > 250
            for key in ("course", "room", "day", "date", "start_time", "end_time")
        ):
            errors.append(f"Review row {index}: invalid field value.")
            continue
        missing = [
            key
            for key in ("course", "room")
            if not row.get(key) or (valid is not None and row[key] not in valid[key])
        ]
        if missing:
            details = "; ".join(
                f"{key}: {str(row.get(key + '_text', '') or 'not detected')[:100]}"
                for key in missing
            )
            errors.append(
                f"Review row {index}: select an existing course and room ({details}). Add missing records, then use Refresh course and room choices; repeated names can be mapped once above the review table."
            )
            continue
        if not row.get("start_time") or not row.get("end_time"):
            errors.append(f"Review row {index}: both start and end time are required.")
            continue
        try:
            if options["mode"] == "weekly":
                weekday = DAYS.index(row.get("day", ""))
                current = first + timedelta(days=(weekday - first.weekday()) % 7)
                dates = []
                while current <= last:
                    if current not in excluded:
                        dates.append(current)
                    current += timedelta(days=7)
                if not dates:
                    errors.append(
                        f"Review row {index}: no {row['day']} occurs within the selected dates after exclusions."
                    )
                    continue
            else:
                selected = date.fromisoformat(row.get("date", ""))
                if row.get("day") and row["day"] != DAYS[selected.weekday()]:
                    errors.append(
                        f"Review row {index}: {selected} is a {DAYS[selected.weekday()]}, not {row['day']}."
                    )
                    continue
                dates = [] if selected in excluded else [selected]
        except ValueError:
            errors.append(
                f"Review row {index}: choose a valid weekday or specific date."
            )
            continue
        for selected in dates:
            result.append(
                {
                    "id": "",
                    "room": row["room"],
                    "course": row["course"],
                    "date": selected.isoformat(),
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "academic_session": session,
                    "cancelled": "false",
                }
            )
            if len(result) > MAX_ROWS:
                raise ImportProblem(
                    f"This teaching period produces more than {MAX_ROWS} classes. Use a shorter period or skip some rows for a separate import."
                )
    if errors:
        raise ImportProblem(errors)
    if not result:
        raise ImportProblem(
            "No classes remain. Keep at least one reviewed row and check excluded dates."
        )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(result)
    return output.getvalue()
