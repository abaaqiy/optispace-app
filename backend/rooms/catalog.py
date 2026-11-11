"""Documented admin choices, not a complete current inventory. See docs/room-catalog.md."""

import json
import re
from pathlib import Path

OTHER_CHOICE = "__other__"
OTHER_BUILDING = OTHER_CHOICE
OTHER_ROOM = OTHER_CHOICE

# Documented buildings/complexes, not room numbers or automatically created rows.
# Sources, historical names and scope are recorded in docs/building-catalog.md.
BUILDING_NAMES = (
    "Faculty of Science Building (White House)",
    "Mathematics Building Complex (Yellow House)",
    "Hezekiah Oluwasanmi Library (HOL)",
    "Oduduwa Hall Complex",
    "Faculty of Arts Block I",
    "Faculty of Arts Block II",
    "Faculty of Arts Block III",
    "Faculty of Administration Building",
    "Faculty of Education Building",
    "Faculty of Law Building",
    "Faculty of Social Sciences Building",
    "Faculty of Agriculture Building",
    "Faculty of Pharmacy Building",
    "Environmental Design and Management Block I (EDM I)",
    "Environmental Design and Management Block II (EDM II)",
    "Biological Sciences Building Complex",
    "Biological Sciences Block X",
    "College of Health Sciences Block Y",
    "College of Health Sciences Block Z",
    "Computer Building Complex",
    "ICT Centre",
    "African Centre of Excellence Building (ACE)",
    "Renewed Hope-NITDA Innovation Hub",
    "Institute of Cultural Studies Building (ICS)",
    "Institute of African Studies Building",
    "Natural History Museum",
    "Nursing Department New Building",
    "Agricultural Economics Building",
    "Science Lecture Theatre Complex",
    "Ajose Lecture Theatre (AJSLT)",
    "First Bank Lecture Theatre (FBLT)",
)

# Functional teaching/study categories, not an official university taxonomy.
# Other teaching/study functions can be entered through Others.
ROOM_TYPES = (
    "Lecture Theatre",
    "Classroom",
    "Tutorial Room",
    "Seminar Room",
    "Auditorium",
    "Amphitheatre",
    "Reading Room",
    "Library",
    "Computer Laboratory",
    "Laboratory",
    "Studio",
    "Demonstration Room",
    "Moot Court",
    "Meeting Room",
)

# Each selectable name has its evidence and search aliases in this checked-in
# catalogue. Loading it never creates database records or changes availability.
ROOM_CATALOGUE = tuple(json.loads(
    (Path(__file__).parent / "data" / "teaching_spaces.json").read_text(encoding="utf-8")
))
ROOM_NAMES = tuple(entry["name"] for entry in ROOM_CATALOGUE)
ROOM_ALIASES = {entry["name"]: tuple(entry["aliases"]) for entry in ROOM_CATALOGUE}


def room_name_key(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def room_catalogue_name(value):
    """Resolve only unambiguous documented names/aliases, never fuzzy guesses."""
    key = room_name_key(value)
    matches = [entry["name"] for entry in ROOM_CATALOGUE
               if key and key in {room_name_key(name) for name in (entry["name"], *entry["aliases"])}]
    return matches[0] if len(matches) == 1 else None


def room_identity_key(value):
    """One identity for spelling/spacing variants and documented room aliases."""
    return room_name_key(room_catalogue_name(value) or value)


# Faculties and colleges used as campus-area choices, including the faculties
# within Health Sciences. These are app navigation choices, not numbered zones.
CAMPUS_ZONES = (
    "College of Health Sciences",
    "Faculty of Administration",
    "Faculty of Agriculture",
    "Faculty of Arts",
    "Faculty of Basic Medical Sciences",
    "Faculty of Clinical Sciences",
    "Faculty of Computing Science and Engineering",
    "Faculty of Dentistry",
    "Faculty of Education",
    "Faculty of Environmental Design and Management",
    "Faculty of Law",
    "Faculty of Pharmacy",
    "Faculty of Science",
    "Faculty of Social Sciences",
    "Faculty of Technology",
    "Postgraduate College",
    # App location categories for buildings outside faculty/college areas.
    "Central Campus",
    "Research and Service Centres",
)
