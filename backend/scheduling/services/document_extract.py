"""Lecture timetable image extraction. Geometry is retained; extracted rows are only drafts.

Never infer a venue from another cell. An unreadable value stays empty and must
be supplied in review. No network services, model APIs or database writes here.
"""

import io
import re
import time
import warnings
from threading import BoundedSemaphore

from PIL import Image

from .image_ocr import Cell, OCR_SECONDS, deadline as _deadline, image_tables
from .timetable_import import ImportProblem

MAX_UPLOAD = 10 * 1024 * 1024
MAX_DRAFT_ROWS = 300
_extract_slots = BoundedSemaphore(1)
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TIME_RANGE = re.compile(
    r"(?<![\w:])(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?\s*[-–—]\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?(?![\w:])",
    re.I,
)


def clock_range(text):
    matches = list(TIME_RANGE.finditer(text.replace("−", "-").replace(".", ":")))
    if len(matches) != 1:
        return "", ""
    a, am, ap, b, bm, bp = matches[0].groups()
    bare_hours = (
        am is None and bm is None and not (a.startswith("0") or b.startswith("0"))
    )
    a, b, am, bm = int(a), int(b), int(am or 0), int(bm or 0)
    if am > 59 or bm > 59:
        return "", ""
    if ap or bp:
        if not ap and bp and bp.upper() == "PM" and a > b and a != 12:
            ap = "AM"
        ap, bp = (ap or bp).upper(), (bp or ap).upper()
        if not (1 <= a <= 12 and 1 <= b <= 12):
            return "", ""
        a, b = a % 12 + (12 if ap == "PM" else 0), b % 12 + (12 if bp == "PM" else 0)
    elif bare_hours:
        # OAU's daytime weekly grids use 12-1, 1-2 ... after 8-9.
        a = a + 12 if 1 <= a <= 7 else a
        b = b + 12 if 1 <= b <= 7 else b
    if not (0 <= a < 24 and 0 <= b < 24 and (a, am) < (b, bm)):
        return "", ""
    return f"{a:02}:{am:02}", f"{b:02}:{bm:02}"


def day_value(text):
    compact = re.sub(r"[^a-z]", "", text.lower())
    matches = [day for day in DAYS if day.lower() in compact]
    return matches[0] if len(matches) == 1 else ""


def heading_label(text):
    """Structural labels only: FRIDAY is a weekday, not a DAY column label."""
    match = re.search(r"\b(COURSE|VENUE|TIME|DAY|CLASS|DATE)\b", text, re.I)
    return match[0].upper() if match else ""


def _code(text):
    # Course and venue can touch: LGS301SRm4. Leave uncertain digits visible.
    match = re.match(r"^([A-Z]{2,5})[ .]*([0-9SOIl!]{3})(?![0-9])", text, re.I)
    if not match:
        return None
    return (match[1].upper() + match[2].upper(), match.end(), not match[2].isdigit())


def _group(cell, page, kind):
    return f"{page}:{kind}:" + ":".join(str(round(value)) for value in cell.box)


def _draft(
    course,
    venue,
    cell,
    page,
    *,
    day_cell,
    time_cell,
    day="",
    start="",
    end="",
    note="",
    lines=None,
):
    words = cell.words if lines is None else lines
    confidence = min((word["confidence"] for word in words), default=cell.confidence)
    box = cell.box
    if words:
        box = (
            min(w["x0"] for w in words),
            min(w["top"] for w in words),
            max(w["x1"] for w in words),
            max(w["bottom"] for w in words),
        )
    return {
        "course_text": course.strip(),
        "room_text": venue.strip(),
        "day": day,
        "date": "",
        "start_time": start,
        "end_time": end,
        "page": page,
        "box": list(box),
        "source": (
            "\n".join(word["text"] for word in words)[:1200]
            if words
            else cell.text[:1200]
        ),
        "note": note,
        "confidence": confidence,
        "day_group": _group(day_cell, page, "day"),
        "day_text": day_cell.text,
        "day_box": list(day_cell.box),
        "day_note": day_cell.note,
        "time_group": _group(time_cell, page, "time"),
        "time_text": time_cell.text,
        "time_box": list(time_cell.box),
        "time_note": time_cell.note,
    }


def _layout(table):
    for i, row in enumerate(table[:5]):
        texts = [cell.text.upper().strip() for cell in row]
        if any("VENUE" in value for value in texts) and any(
            "DATE" in value for value in texts
        ):
            raise ImportProblem(
                "This is a dated/examination layout. Upload a weekly lecture timetable image; dated lectures can still use CSV."
            )
        if sum("COURSE" in value for value in texts) >= 2:
            return "columns", i, None
        if sum(bool(clock_range(value)[0]) for value in texts) >= 2 and (
            i == 0 or any(heading_label(value) in {"DAY", "CLASS"} for value in texts)
        ):
            return (
                "rows",
                i,
                next((j for j, value in enumerate(texts) if "CLASS" in value), None),
            )
    # Recognise a weekday grid even when a low-resolution COURSE label was missed.
    if len(table[0]) >= 5 and len(table[0]) % 2 == 1:
        headings = {id(cell): cell for cell in table[0]}.values()
        day_count = sum(bool(day_value(cell.text)) for cell in headings)
        subheadings = [cell.text.upper() for cell in table[1]] if len(table) > 1 else []
        if (
            day_count >= 2
            or day_count
            and sum("VENUE" in value for value in subheadings) >= 2
        ):
            return "columns", 1, None
    texts = [cell.text.upper() for cell in table[0]]
    if any(heading_label(value) in {"DAY", "CLASS"} for value in texts):
        return (
            "rows",
            0,
            next((j for j, value in enumerate(texts) if "CLASS" in value), None),
        )
    return None, -1, None


def parse_table(table, page=1, continuation=None, layout="auto"):
    """Keep weekly class/venue pairs inside their original row or cell."""
    drafts, notices = [], []
    if not table or not table[0]:
        return drafts, notices, continuation
    kind, header, classcol = _layout(table)
    continued = False
    # Only inherit weekday columns from a preceding, vertically aligned section.
    # Matching the number of columns alone could attach an unrelated table.
    boundaries = [max(row[c].box[0] for row in table) for c in range(len(table[0]))] + [
        table[0][-1].box[2]
    ]
    can_continue = (
        kind is None
        and continuation
        and len(table[0]) == continuation["width"]
        and page == continuation["page"]
        and table[0][0].box[1] >= continuation["bottom"]
        and all(
            abs(a - b) <= max(5, (boundaries[-1] - boundaries[0]) * 0.02)
            for a, b in zip(boundaries, continuation["boundaries"])
        )
    )
    if can_continue and layout != "rows":
        kind, header, continued = "columns", -1, True
        notices.append(
            f"Image {page}: continuation uses the previous table's weekday headings. Check these once in Shared headings."
        )
    if layout != "auto" and not continued:
        if kind != layout:
            header = 1 if layout == "columns" else 0
        kind = layout
        classcol = (
            1
            if layout == "rows"
            and len(table[0]) > 1
            and heading_label(table[0][1].text) == "CLASS"
            else None
        )
    if kind is None:
        return (
            [],
            [
                f"Image {page}: layout not recognised. Select the matching layout and extract again, or add entries beside the image."
            ],
            continuation,
        )
    seen = set()
    if kind == "columns":
        if continued:
            pairs = continuation["pairs"]
        else:
            pairs = []
            for c in range(1, len(table[0]) - 1, 2):
                heading = table[0][c]
                pairs.append((c, c + 1, heading))
        # A separate table section must supply its own times; never carry the
        # previous section's last time into a cropped or unreadable first row.
        time_cell = None
        current_time = ("", "")
        for row in table[header + 1 :]:
            clock_text = row[0].text.strip(" |_~")
            if clock_text or row[0].has_content or row[0].note:
                time_cell, current_time = row[0], clock_range(clock_text)
            if time_cell is None:
                time_cell = row[0]
            start, end = current_time
            for c, v, heading in pairs:
                if v >= len(row):
                    continue
                cell, venue = row[c], row[v]
                if not cell.text.strip() or "COURSE" in cell.text.upper():
                    continue
                identity = (id(cell), id(venue), start, end, c)
                if identity in seen:
                    continue
                seen.add(identity)
                text = " ".join(cell.text.split())
                code = _code(text)
                course = code[0] if code and not text[code[1] :].strip() else text
                combined = Cell(
                    f"{cell.text} | {venue.text}",
                    (
                        cell.box[0],
                        cell.box[1],
                        venue.box[2],
                        max(cell.box[3], venue.box[3]),
                    ),
                    min(
                        (
                            value
                            for value in (cell.confidence, venue.confidence)
                            if value is not None
                        ),
                        default=None,
                    ),
                    cell.words + venue.words,
                )
                note = (
                    "Check the detected course code."
                    if not code or code[2] or text[code[1] :].strip()
                    else ""
                )
                drafts.append(
                    _draft(
                        course,
                        " ".join(venue.text.split()),
                        combined,
                        page,
                        day_cell=heading,
                        time_cell=time_cell,
                        day=day_value(heading.text),
                        start=start,
                        end=end,
                        note=note,
                    )
                )
        return (
            drafts,
            notices,
            {
                "width": len(table[0]),
                "pairs": pairs,
                "page": page,
                "boundaries": boundaries,
                "bottom": max(cell.box[3] for cell in table[-1]),
            },
        )
    first = classcol + 1 if classcol is not None else 1
    for row in table[header + 1 :]:
        heading = row[0]
        day = day_value(heading.text)
        for c in range(first, len(row)):
            cell, time_cell = row[c], table[header][c]
            if not cell.text.strip() or (id(cell), c) in seen:
                continue
            seen.add((id(cell), c))
            start, end = clock_range(time_cell.text)
            if classcol is not None:
                # Each administration cell represents one course and its own venue.
                text = " ".join(cell.text.split()).strip(" |[]~")
                code = _code(text)
                course, venue, note = (
                    text,
                    "",
                    "Check the course and room in this cell.",
                )
                if code:
                    course, venue = code[0], text[code[1] :].strip(" /,;:.")
                    note = "Check the detected course code." if code[2] else ""
                drafts.append(
                    _draft(
                        course,
                        venue,
                        cell,
                        page,
                        day_cell=heading,
                        time_cell=time_cell,
                        day=day,
                        start=start,
                        end=end,
                        note=note,
                    )
                )
                continue
            # Law cells contain alternating course and venue lines, sometimes wrapped.
            lines = [
                line.strip(" |[]‘’“”~©")
                for line in cell.text.splitlines()
                if line.strip(" |[]‘’“”~©")
            ]
            k = 0
            while k < len(lines):
                begin = k
                code = _code(lines[k])
                if not code or code[0].startswith("LAW"):
                    drafts.append(
                        _draft(
                            lines[k],
                            "",
                            cell,
                            page,
                            day_cell=heading,
                            time_cell=time_cell,
                            day=day,
                            start=start,
                            end=end,
                            note="Unrecognised text; check this cell.",
                            lines=(
                                cell.words[k : k + 1]
                                if len(cell.words) == len(lines)
                                else None
                            ),
                        )
                    )
                    k += 1
                    continue
                course, venue = code[0], lines[k][code[1] :].strip(" /,;:.")
                if not venue and k + 1 < len(lines):
                    next_code = _code(lines[k + 1])
                    if not next_code or next_code[0].startswith("LAW"):
                        k += 1
                        venue = lines[k]
                        while k + 1 < len(lines) and lines[k + 1].upper() in {
                            "COURT",
                            "HALL",
                            "THEATRE",
                        }:
                            k += 1
                            venue += " " + lines[k]
                selected = (
                    cell.words[begin : k + 1] if len(cell.words) == len(lines) else None
                )
                drafts.append(
                    _draft(
                        course,
                        venue,
                        cell,
                        page,
                        day_cell=heading,
                        time_cell=time_cell,
                        day=day,
                        start=start,
                        end=end,
                        note="Check the detected course code." if code[2] else "",
                        lines=selected,
                    )
                )
                k += 1
    return drafts, notices, None


def _extract_document(upload, *, layout="auto"):
    if upload.size > MAX_UPLOAD:
        raise ImportProblem("Upload a PNG or JPEG of at most 10 MB.")
    raw = upload.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise ImportProblem("Upload a file of at most 10 MB.")
    pages, all_rows, notices, context = [], [], [], None

    def collect(image, tables, warning=""):
        nonlocal context
        number = len(pages) + 1
        if warning:
            notices.append(f"Page {number}: {warning}")
        for table in tables:
            rows, problems, context = parse_table(table, number, context, layout=layout)
            all_rows.extend(rows)
            notices.extend(problems)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=85)
        pages.append(
            {"image": output.getvalue(), "width": image.width, "height": image.height}
        )

    deadline_token = _deadline.set(time.monotonic() + OCR_SECONDS)
    try:
        if raw.startswith(b"%PDF-"):
            raise ImportProblem(
                "PDF uploads are no longer supported. Upload a PNG or JPEG lecture timetable image."
            )
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise ImportProblem("Use a PNG or JPEG lecture timetable image.")
                collect(*image_tables(image))
    except ImportProblem:
        raise
    except Exception as error:
        raise ImportProblem(
            "This image could not be read. Use a clear PNG or JPEG lecture timetable image."
        ) from error
    finally:
        _deadline.reset(deadline_token)
    if len(all_rows) > MAX_DRAFT_ROWS:
        raise ImportProblem(
            f"This document contains more than {MAX_DRAFT_ROWS} entries. Split it into smaller files with their headings."
        )
    if not all_rows:
        notices.append(
            "No entries were extracted. You can add rows manually beside the source, or upload a clearer document."
        )
    notices.append(
        "Match repeated names and check shared day/time headings once. Review the clear groups beside the image and correct flagged entries; also check for omitted cells. Blank cells do not prove a shared room is free."
    )
    return {"rows": all_rows, "pages": pages, "notices": list(dict.fromkeys(notices))}


def extract_document(upload, *, layout="auto"):
    if layout not in {"auto", "columns", "rows"}:
        raise ImportProblem("Choose a supported lecture timetable layout.")
    if not _extract_slots.acquire(blocking=False):
        raise ImportProblem(
            "Another timetable image is being read. Please try again in a minute."
        )
    try:
        return _extract_document(upload, layout=layout)
    finally:
        _extract_slots.release()
