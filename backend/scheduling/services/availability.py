from dataclasses import dataclass
from datetime import datetime, time, timedelta
from math import ceil

from django.utils import timezone


@dataclass(frozen=True)
class RoomSession:
    start_time: time
    end_time: time
    title: str
    status: str


def build_availability(entries, at, *, reservations=(), has_school_timetable):
    """Classes occupy rooms; approved bookings reserve only their exact intervals."""
    result = {
        "status": "unknown",
        "statusText": "No school timetable has been entered for this date",
        "currentSchedule": None,
        "nextSchedule": None,
        "hourlySchedule": [],
        "reservedUntil": None,
        "reservedSeconds": None,
        "statusTimeline": [],
    }
    sessions = [
        RoomSession(entry.start_time, entry.end_time, entry.title, "occupied")
        for entry in entries
        if not entry.is_cancelled
    ]
    sessions.extend(
        # Keep private booking purposes and requester details out of public schedules.
        RoomSession(
            booking.start_time, booking.end_time, "Approved reservation", "reserved"
        )
        for booking in reservations
        if not booking.is_cancelled
    )
    sessions.sort(key=lambda item: item.start_time)
    if not has_school_timetable and not sessions:
        return result

    zone = timezone.get_default_timezone()

    def moment(clock):
        return timezone.make_aware(datetime.combine(at.date(), clock), zone)

    start = moment(time.min)
    end = start + timedelta(days=1)

    def state(when):
        current = next(
            (
                item
                for item in sessions
                if moment(item.start_time) <= when < moment(item.end_time)
            ),
            None,
        )
        upcoming = next(
            (item for item in sessions if moment(item.start_time) > when), None
        )
        values = {
            "currentSchedule": current.title if current else None,
            "nextSchedule": (
                f"{upcoming.start_time:%H:%M} - {upcoming.title}"
                if upcoming
                else "No further scheduled sessions today"
            ),
            "reservedUntil": None,
            "reservedSeconds": None,
        }
        if current and current.status == "reserved":
            values.update(
                status="reserved",
                statusText=f"Reserved: Approved reservation until {current.end_time:%H:%M}",
                reservedUntil=moment(current.end_time).isoformat(),
                reservedSeconds=ceil((moment(current.end_time) - when).total_seconds()),
            )
        elif current:
            values.update(
                status="occupied",
                statusText=f"Scheduled: {current.title} until {current.end_time:%H:%M}",
            )
        elif not has_school_timetable:
            values.update(
                status="unknown",
                statusText="No school timetable has been entered for this date; approved reservations are shown",
            )
        else:
            free_until = moment(upcoming.start_time) if upcoming else end
            until = f"{free_until:%H:%M}" if free_until < end else "the end of the day"
            values.update(
                status="available",
                statusText=f"No active class or approved reservation — available until {until}",
            )
        return values

    boundaries = {start, end}
    for session in sessions:
        for value in (moment(session.start_time), moment(session.end_time)):
            if start < value < end:
                boundaries.add(value)
    boundaries = sorted(boundaries)
    for left, right in zip(boundaries, boundaries[1:]):
        values = state(left)
        result["statusTimeline"].append(
            {"start": left.isoformat(), "end": right.isoformat(), **values}
        )
        event = (
            values["currentSchedule"]
            if values["status"] == "occupied"
            else (
                values["statusText"]
                if values["status"] in {"reserved", "unknown"}
                else "Timetable free slot"
            )
        )
        result["hourlySchedule"].append(
            {
                "time": f"{left:%H:%M} - {right:%H:%M}",
                "event": event,
                "status": values["status"],
                # Retain the legacy non-available flag; status distinguishes each state.
                "occupied": values["status"] != "available",
                "reserved": values["status"] == "reserved",
            }
        )
    result.update(state(at))
    return result
