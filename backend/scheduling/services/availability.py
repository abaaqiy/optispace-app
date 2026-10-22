from datetime import datetime, timedelta


SOON_WINDOW = timedelta(minutes=60)


def make_slot(start, end, event, occupied):
    return {
        "time": f"{start:%H:%M} - {end:%H:%M}",
        "event": event,
        "occupied": occupied,
    }


def build_availability(timetable, allocations, at_time):
    """Calculate one room's status using its timetable for the chosen date."""

    result = {
        "status": "unknown",
        "statusText": "No published timetable for this date",
        "currentSchedule": None,
        "nextSchedule": None,
        "hourlySchedule": [],
    }

    if timetable is None or not timetable.is_published:
        return result

    sessions = sorted(
        (item for item in allocations if not item.is_cancelled),
        key=lambda item: item.start_time,
    )

    # Build the full schedule, including gaps within verified coverage.
    cursor = timetable.coverage_start

    for session in sessions:
        if cursor < session.start_time:
            result["hourlySchedule"].append(
                make_slot(
                    cursor,
                    session.start_time,
                    "Timetable free slot",
                    False,
                )
            )

        result["hourlySchedule"].append(
            make_slot(
                session.start_time,
                session.end_time,
                session.title,
                True,
            )
        )
        cursor = session.end_time

    if cursor < timetable.coverage_end:
        result["hourlySchedule"].append(
            make_slot(
                cursor,
                timetable.coverage_end,
                "Timetable free slot",
                False,
            )
        )

    # Coverage includes its start, but not its end.
    if not timetable.coverage_start <= at_time < timetable.coverage_end:
        result["statusText"] = "Outside published timetable coverage"
        return result

    current = next(
        (
            session
            for session in sessions
            if session.start_time <= at_time < session.end_time
        ),
        None,
    )

    upcoming = next(
        (
            session
            for session in sessions
            if session.start_time > at_time
        ),
        None,
    )

    if upcoming:
        result["nextSchedule"] = (
            f"{upcoming.start_time:%H:%M} - {upcoming.title}"
        )
    else:
        result["nextSchedule"] = (
            "No further sessions in this coverage window"
        )

    if current:
        result["status"] = "occupied"
        result["statusText"] = (
            f"Scheduled: {current.title} until {current.end_time:%H:%M}"
        )
        result["currentSchedule"] = current.title
        return result

    free_until = (
        upcoming.start_time if upcoming else timetable.coverage_end
    )

    result["status"] = "available"
    result["statusText"] = (
        f"Timetable-available until {free_until:%H:%M}"
    )

    if upcoming:
        waiting_time = (
            datetime.combine(timetable.date, upcoming.start_time)
            - datetime.combine(timetable.date, at_time)
        )

        if waiting_time <= SOON_WINDOW:
            result["status"] = "soon"

    return result

