from datetime import datetime, time, timedelta
from math import ceil

from django.utils import timezone


RESERVED_WINDOW = timedelta(minutes=15)
RESERVED_ROOM_TYPES = {"seminar room", "seminar hall", "event hall"}


def build_availability(entries, at, *, room_type, has_school_timetable):
    """Check all active classes for a room; warnings apply only to eligible halls."""
    result = {
        "status": "unknown", "statusText": "No school timetable has been entered for this date",
        "currentSchedule": None, "nextSchedule": None, "hourlySchedule": [],
        "reservedUntil": None, "reservedSeconds": None, "statusTimeline": [],
    }
    if not has_school_timetable:
        return result

    zone = timezone.get_default_timezone()
    def moment(clock):
        return timezone.make_aware(datetime.combine(at.date(), clock), zone)

    start = moment(time.min)
    end = start + timedelta(days=1)
    sessions = sorted((item for item in entries if not item.is_cancelled), key=lambda item: item.start_time)
    warning_window = RESERVED_WINDOW if room_type.strip().casefold() in RESERVED_ROOM_TYPES else timedelta(0)

    def state(when):
        current = next((item for item in sessions if moment(item.start_time) <= when < moment(item.end_time)), None)
        upcoming = next((item for item in sessions if moment(item.start_time) > when), None)
        values = {
            "currentSchedule": current.title if current else None,
            "nextSchedule": f"{upcoming.start_time:%H:%M} - {upcoming.title}" if upcoming else "No further classes today",
            "reservedUntil": None, "reservedSeconds": None,
        }
        if upcoming and moment(upcoming.start_time) - when <= warning_window:
            values.update(
                status="reserved", statusText=f"Reserved for {upcoming.title} at {upcoming.start_time:%H:%M}",
                reservedUntil=moment(upcoming.start_time).isoformat(),
                reservedSeconds=ceil((moment(upcoming.start_time) - when).total_seconds()),
            )
        elif current:
            values.update(status="occupied", statusText=f"Scheduled: {current.title} until {current.end_time:%H:%M}")
        else:
            free_until = max(start, moment(upcoming.start_time) - warning_window) if upcoming else end
            until = f"{free_until:%H:%M}" if free_until < end else "the end of the day"
            values.update(status="available", statusText=f"No active class scheduled — available until {until}")
        return values

    boundaries = {start, end}
    for session in sessions:
        for value in (moment(session.start_time) - warning_window, moment(session.start_time), moment(session.end_time)):
            if start < value < end:
                boundaries.add(value)
    boundaries = sorted(boundaries)
    for left, right in zip(boundaries, boundaries[1:]):
        values = state(left)
        result["statusTimeline"].append({"start": left.isoformat(), "end": right.isoformat(), **values})
        event = values["currentSchedule"] if values["status"] == "occupied" else values["statusText"] if values["status"] == "reserved" else "Timetable free slot"
        if values["status"] == "reserved" and values["currentSchedule"]:
            event += f" (currently: {values['currentSchedule']})"
        result["hourlySchedule"].append({
            "time": f"{left:%H:%M} - {right:%H:%M}", "event": event,
            "occupied": values["status"] != "available", "reserved": values["status"] == "reserved",
        })
    result.update(state(at))
    return result
