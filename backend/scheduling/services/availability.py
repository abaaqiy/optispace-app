from datetime import datetime, timedelta
from types import SimpleNamespace


SOON_WINDOW = timedelta(minutes=60)


def make_slot(start, end, event, occupied, reserved=False):
    return {
        "time": f"{start:%H:%M} - {end:%H:%M}",
        "event": event,
        "occupied": occupied,
        "reserved": reserved,
    }


def build_availability(timetable, allocations, at_time, reservations=()):
    """Published lecture coverage plus approved reservations, with private purposes hidden."""
    result = {
        "status": "unknown",
        "statusText": "No published timetable for this date",
        "currentSchedule": None,
        "nextSchedule": None,
        "hourlySchedule": [],
    }
    published = timetable is not None and timetable.is_published
    sessions = [
        SimpleNamespace(start_time=item.start_time, end_time=item.end_time, title=item.title, reserved=False)
        for item in allocations if published and not item.is_cancelled
    ]
    sessions.extend(
        SimpleNamespace(start_time=item.start_time, end_time=item.end_time, title="Reserved", reserved=True)
        for item in reservations if item.status == "approved"
    )
    sessions.sort(key=lambda item: item.start_time)

    # Only report free gaps inside a published coverage window. Approved
    # reservations remain visible if an administrator later unpublishes a day.
    cursor = timetable.coverage_start if published else None
    for session in sessions:
        if published and cursor < session.start_time:
            gap_end = min(session.start_time, timetable.coverage_end)
            if cursor < gap_end:
                result["hourlySchedule"].append(make_slot(cursor, gap_end, "Timetable free slot", False))
        result["hourlySchedule"].append(make_slot(
            session.start_time, session.end_time, session.title, True, session.reserved,
        ))
        if published:
            cursor = max(cursor, session.end_time)
    if published and cursor < timetable.coverage_end:
        result["hourlySchedule"].append(make_slot(cursor, timetable.coverage_end, "Timetable free slot", False))

    current = next((item for item in sessions if item.start_time <= at_time < item.end_time), None)
    upcoming = next((item for item in sessions if item.start_time > at_time), None)
    if current and current.reserved:
        result.update(status="reserved", statusText=f"Reserved until {current.end_time:%H:%M}", currentSchedule="Reserved")
        if upcoming:
            result["nextSchedule"] = f"{upcoming.start_time:%H:%M} - {upcoming.title}"
        return result
    if not published:
        return result
    if not timetable.coverage_start <= at_time < timetable.coverage_end:
        result["statusText"] = "Outside published timetable coverage"
        return result

    result["nextSchedule"] = (
        f"{upcoming.start_time:%H:%M} - {upcoming.title}" if upcoming
        else "No further sessions in this coverage window"
    )
    if current:
        result.update(
            status="occupied", statusText=f"Scheduled: {current.title} until {current.end_time:%H:%M}",
            currentSchedule=current.title,
        )
        return result

    free_until = min(upcoming.start_time, timetable.coverage_end) if upcoming else timetable.coverage_end
    result.update(status="available", statusText=f"Timetable-available until {free_until:%H:%M}")
    if upcoming:
        waiting_time = datetime.combine(timetable.date, upcoming.start_time) - datetime.combine(timetable.date, at_time)
        if waiting_time <= SOON_WINDOW:
            result["status"] = "soon"
    return result
