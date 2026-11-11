"""Stage missing references without writes; confirm the whole image atomically."""
import hashlib
import json
import re

from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from rooms.catalog import room_identity_key
from rooms.models import Building, Room
from scheduling.models import Course, TimetableDay, TimetableImageImport

from .document_review import normalise, references, reviewed_csv
from .locking import lock_rooms
from .semesters import semester_options
from .timetable_import import (
    ImportProblem, build_plan, parse_csv, resolve_rows,
)

MAX_IMAGE_CLASSES = 16000  # Up to 300 weekly slots through a full teaching year.


def parse_image_rows(text):
    return parse_csv(text, max_rows=MAX_IMAGE_CLASSES, max_bytes=8 * 1024 * 1024)


class NewCourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ("code", "title", "department", "title_pending")

    def clean_code(self):
        value = re.sub(r"\s+", "", self.cleaned_data["code"]).upper()
        if not re.fullmatch(r"[A-Z]{2,5}\d{3}", value):
            raise forms.ValidationError("Use a course code such as CHM102; check uncertain characters.")
        return value


class NewRoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ("name", "building", "room_number", "room_type", "capacity", "size_category", "facilities")


class NewBuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = ("name", "campus_zone")


def check_metadata(options):
    for key, length in (("department", 150), ("faculty", 150), ("semester", 20), ("source_version", 100)):
        value = options.get(key, "")
        if not isinstance(value, str) or len(value) > length:
            raise ImportProblem(f"Check {key.replace('_', ' ')} (at most {length} characters).")
    if options.get("semester", "") not in {"", "Rain", "Harmattan"}:
        raise ImportProblem("Choose Rain or Harmattan semester, or leave it blank if not identified.")


def stage_references(pending, rows, user):
    if not isinstance(pending, dict) or set(pending) - {"buildings", "courses", "rooms"}:
        raise ImportProblem("The proposed course/room records could not be read.")
    staged, refs = {"buildings": [], "courses": [], "rooms": []}, references()
    new_buildings = {}
    used = {kind: {row.get(field) for row in rows if not row.get("skip") and isinstance(row.get(field), str)}
            for kind, field in (("courses", "course"), ("rooms", "room"))}
    errors, keys = [], set()
    seen = {
        "courses": {normalise(code) for code in Course.objects.values_list("code", flat=True)},
        "rooms": set(Room.objects.values_list("name_key", flat=True)),
    }
    building_proposals = {}
    buildings = pending.get('buildings', [])
    if not isinstance(buildings, list) or len(buildings) > 300:
        raise ImportProblem('Prepare at most 300 buildings per image.')
    for data in buildings:
        if not isinstance(data, dict):
            raise ImportProblem('A proposed building is invalid.')
        key = data.get('key', '')
        if not isinstance(key, str) or not re.fullmatch(r'draft-building-[a-f0-9-]{8,40}', key) or key in keys:
            raise ImportProblem('A proposed building has an invalid or repeated identifier.')
        keys.add(key)
        building_proposals[key] = data

    def prepare_building(data):
        if not user.has_perm('rooms.add_building'):
            raise ImportProblem('You do not have permission to create buildings.')
        if any(not isinstance(data.get(name, ''), str) for name in ('name', 'campus_zone')):
            raise ImportProblem('A proposed building contains invalid field values.')
        building_form = NewBuildingForm(data=data)
        if not building_form.is_valid():
            errors.extend(f"New building: {name}: {'; '.join(messages)}"
                          for name, messages in building_form.errors.items())
            return None
        candidate = building_form.save(commit=False)
        if Building.objects.filter(name__iexact=candidate.name).exists():
            errors.append(f'Building {candidate.name} already exists. Select the saved building.')
            return None
        bkey = normalise(candidate.name)
        building = new_buildings.get(bkey)
        if building and building.campus_zone != candidate.campus_zone:
            errors.append(f'Building {candidate.name} has conflicting campus areas in the proposed rooms.')
            return None
        if not building:
            building = candidate
            building.pk = -(len(new_buildings) + 1)
            new_buildings[bkey] = building
            staged['buildings'].append((bkey, building, building_form))
        return building

    resolved_buildings = {}
    for kind, model, form_type, field in (
        ("courses", Course, NewCourseForm, "code"), ("rooms", Room, NewRoomForm, "name"),
    ):
        records = pending.get(kind, [])
        if not isinstance(records, list) or len(records) > 300:
            raise ImportProblem("Prepare at most 300 courses or rooms per image.")
        for data in records:
            if not isinstance(data, dict):
                raise ImportProblem("A proposed record is invalid.")
            key = data.get("key", "")
            if not isinstance(key, str) or not re.fullmatch(r"draft-(?:course|room)-[a-f0-9-]{8,40}", key) or key in keys:
                raise ImportProblem("A proposed record has an invalid or repeated identifier.")
            keys.add(key)
            # Discard unreferenced drafts, e.g. after skipping their last class.
            if key not in used[kind]:
                continue
            if data.get('duplicate_of'):
                errors.append(f"Select the existing {kind[:-1]} instead of an earlier duplicate proposal.")
                continue
            if kind == "courses" and not isinstance(data.get("title_pending", False), bool):
                raise ImportProblem("Confirm whether the course title is awaiting confirmation using the checkbox.")
            if any(not isinstance(data.get(name, ""), (str, int)) for name in form_type._meta.fields if name != "facilities"):
                raise ImportProblem("A proposed course or room contains invalid field values.")
            if kind == "rooms" and (not isinstance(data.get("facilities", []), list) or any(
                not isinstance(value, (str, int)) for value in data.get("facilities", [])
            )):
                raise ImportProblem("Select valid room facilities.")
            if not user.has_perm(f"{model._meta.app_label}.add_{model._meta.model_name}"):
                raise ImportProblem(f"You do not have permission to create {kind}. Match a saved record instead.")
            building = None
            if kind == "rooms" and data.get("building") == "new":
                # Backward compatibility for drafts with per-room building details.
                building = prepare_building({
                    "name": data.get("building_name", ""), "campus_zone": data.get("campus_zone", ""),
                })
                if building is None:
                    continue
            elif kind == 'rooms' and str(data.get('building', '')).startswith('draft-building-'):
                building_key = data['building']
                if building_key not in building_proposals:
                    errors.append(f"New room {data.get('name', '')}: select a building; its prepared building is missing.")
                    continue
                if building_key not in resolved_buildings:
                    resolved_buildings[building_key] = prepare_building(building_proposals[building_key])
                building = resolved_buildings[building_key]
                if building is None:
                    continue
            form = form_type(data=data, **({"instance": Room(building=building)} if building else {}))
            if building:
                del form.fields["building"]
            if not form.is_valid():
                errors.extend(f"New {kind[:-1]} {str(data.get(field, ''))[:100]}: {name}: {'; '.join(messages)}"
                              for name, messages in form.errors.items())
                continue
            obj = form.save(commit=False)
            identity = room_identity_key(obj.name) if kind == "rooms" else normalise(obj.code)
            if identity in seen[kind]:
                errors.append(f"{obj}: already exists or repeats another proposed {kind[:-1]}. Match it once instead.")
                continue
            seen[kind].add(identity)
            # Negative IDs allow the ordinary timetable planner to check new
            # rooms/courses without creating anything during preview.
            obj.pk = -(len(staged[kind]) + 1)
            if kind == "rooms":
                obj.code = key
            staged[kind].append((key, obj, form))
            refs[kind].append({"value": obj.code, "label": str(obj), "keys": []})
    if errors:
        raise ImportProblem(errors)
    return staged, refs


def image_plan(rows, options, pending, user):
    options = semester_options(options)
    check_metadata(options)
    staged, refs = stage_references(pending, rows, user)
    replacements = {kind[:-1]: {key: obj.code for key, obj, _ in staged[kind]} for kind in ("courses", "rooms")}
    translated = []
    for row in rows:
        copy = row.copy()
        for field in ("course", "room"):
            if isinstance(copy.get(field), str):
                copy[field] = replacements[field].get(copy[field], copy[field])
        translated.append(copy)
    text = reviewed_csv(translated, options, refs=refs, max_rows=MAX_IMAGE_CLASSES)
    plan = build_plan(resolve_rows(
        parse_image_rows(text), extra_rooms=[obj for _, obj, _ in staged["rooms"]],
        extra_courses=[obj for _, obj, _ in staged["courses"]],
    ))
    snapshot = json.dumps({"plan": plan.fingerprint, "pending": pending, "options": options}, sort_keys=True)
    fingerprint = hashlib.sha256(snapshot.encode()).hexdigest()
    return plan, staged, text, fingerprint


def apply_image(rows, options, pending, expected, user, filename, log):
    try:
        with transaction.atomic():
            # Serialize image imports creating the same reference names. Room
            # locks below also coordinate with reservations and CSV imports.
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [739184020])
            options = semester_options(options, lock=True)
            plan, staged, text, fingerprint = image_plan(rows, options, pending, user)
            existing_rooms = {row.room.pk for row in plan.rows if row.room.pk > 0}
            with lock_rooms(existing_rooms):
                building_ids = {obj.building_id for _, obj, _ in staged["rooms"] if obj.building_id > 0}
                list(Building.objects.select_for_update().filter(pk__in=building_ids).order_by("pk"))
                course_ids = {row.course.pk for row in plan.rows if row.course.pk > 0}
                list(Course.objects.select_for_update().filter(pk__in=course_ids).order_by("pk"))
                plan, staged, text, fingerprint = image_plan(rows, options, pending, user)
                if fingerprint != expected:
                    raise ImportProblem("The semester settings, records, timetable or approved reservations changed after preview. Validate again.")
                for entries in staged.values():
                    for _, obj, form in entries:
                        obj.pk = None
                        if isinstance(obj, Room):
                            obj.building_id = obj.building.pk
                        obj.save()
                        form.save_m2m()
                        log(obj, "Add")
                # Recheck conflicts and lock saved timetable rows before writes.
                final = build_plan(resolve_rows(parse_image_rows(text)), lock_entries=True)
                new_rows = [row for row in final.rows if row.action == "Add"]
                source = None
                if new_rows:
                    source = TimetableImageImport.objects.create(
                        filename=filename[:255],
                        teaching_semester_id=options['teaching_semester'],
                        **{key: options.get(key, "").strip() for key in (
                            "department", "faculty", "academic_session", "semester", "source_version",
                            "first_date", "last_date", "exclude_dates",
                        )},
                    )
                for row in new_rows:
                    entry = TimetableDay(**row.values, image_import=source)
                    entry.save()
                    log(entry, "Add")
                return {**final.counts, **{key: len(value) for key, value in staged.items()}}
    except (ValidationError, IntegrityError) as error:
        raise ImportProblem("A record changed or is invalid. Nothing was imported. Validate the draft again.") from error
