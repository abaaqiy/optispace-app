from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bookings.models import Reservation
from bookings.services import change_reservation
from scheduling.models import TimetableDay

from .catalog import (
    CAMPUS_ZONES, OTHER_CHOICE, ROOM_ALIASES, ROOM_CATALOGUE, ROOM_NAMES, ROOM_TYPES,
    room_catalogue_name,
)
from .forms import RoomAdminForm
from .models import Building, Facility, Room


class RoomAdminFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="catalog-admin", email="catalog-admin@oauife.edu.ng", password="Quartz-Admin-581!",
        )
        cls.building = Building.objects.create(name="Existing building", campus_zone="Existing area")
        cls.room = Room.objects.create(
            code="stable-room-url", name="Existing custom room",
            room_type="Old room type", capacity=50, size_category="large", building=cls.building,
        )
        cls.day = TimetableDay.objects.create(
            room=cls.room, date=date(2030, 1, 5), start_time=time(8), end_time=time(18),
        )
        cls.facility = Facility.objects.create(code="projector")

    def setUp(self):
        self.client.force_login(self.admin)

    def data(self, **changes):
        data = {
            "name_0": "First Bank Lecture Theatre (FBLT)", "name_1": "",
            "room_type_0": "Lecture Theatre", "room_type_1": "", "building": self.building.pk,
            "capacity": "100", "size_category": "large", "facilities": [self.facility.pk],
            "_save": "Save",
        }
        data.update(changes)
        return data

    def test_catalogue_is_documented_unique_and_has_others_last(self):
        form = RoomAdminForm()
        self.assertGreater(len(ROOM_NAMES), 100)
        self.assertEqual(len(ROOM_NAMES), len(set(ROOM_NAMES)))
        self.assertTrue(all(row["source"] and row["location"] for row in ROOM_CATALOGUE))
        choices = list(form.fields["name"].widget.widgets[0].choices)
        self.assertEqual(set(dict(choices)) - {"", OTHER_CHOICE}, set(ROOM_NAMES) | {self.room.name})
        self.assertEqual(choices[-1][0], OTHER_CHOICE)
        self.assertNotIn("zone", form.fields)
        self.assertTrue(form.fields["building"].required)
        self.assertIn("Chemistry Lecture Theatre 102 (CH 102)", ROOM_NAMES)
        self.assertIn("Local Government Studies Reading Room", ROOM_NAMES)
        self.assertNotIn("Health Sciences Lecture Theatre (HSLT)", ROOM_NAMES)
        self.assertFalse(any("Staff School" in name or "Moro" in name for name in ROOM_NAMES))
        self.assertFalse(any(word in name for name in ROOM_NAMES for word in ("Hostel", "Bedroom")))

    def test_add_page_hides_code_and_renders_all_dropdowns(self):
        response = self.client.get(reverse("admin:rooms_room_add"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="code"')
        self.assertContains(response, '<select name="name_0"')
        self.assertContains(response, 'name="name_1"')
        self.assertContains(response, 'value="__other__"', count=2)
        self.assertContains(response, 'Custom room name (for Others)')
        self.assertContains(response, 'Custom room type (for Others)')
        self.assertContains(response, '<select name="room_type_0"')
        self.assertContains(response, 'rooms/catalog.js', count=1)
        self.assertContains(response, 'select2.full', count=1)
        self.assertContains(response, 'vendor/jquery/jquery', count=1)

    def test_add_selected_room_generates_code_and_saves_facilities(self):
        response = self.client.post(reverse("admin:rooms_room_add"), self.data(code="forged-code"))
        self.assertEqual(response.status_code, 302)
        room = Room.objects.get(name="First Bank Lecture Theatre (FBLT)")
        self.assertNotEqual(room.code, "forged-code")
        self.assertLessEqual(len(room.code), 50)
        room.full_clean()
        self.assertEqual(list(room.facilities.all()), [self.facility])
        data = self.client.get(f"/api/rooms/{room.code}/").json()
        self.assertEqual(data["name"], room.name)
        self.assertEqual(data["zone"], self.building.campus_zone)

    def test_selecting_catalogue_name_keeps_room_url_schedule_and_reservation(self):
        lecturer = get_user_model().objects.create_user(
            username="room-lecturer", email="room-lecturer@oauife.edu.ng", role="lecturer",
        )
        reservation = Reservation.objects.create(
            room=self.room, user=lecturer, date=self.day.date, start_time=time(18),
            end_time=time(19), purpose="Existing reservation",
        )
        change_reservation(reservation.reference, self.admin, "approve")
        new_building = Building.objects.create(name="Updated building", campus_zone=CAMPUS_ZONES[0])
        new_facility = Facility.objects.create(code="wifi")
        self.room.facilities.add(self.facility)
        room_count = Room.objects.count()
        list_page = self.client.get(reverse("admin:rooms_room_changelist"))
        self.assertContains(list_page, 'aria-label="Edit room: Existing custom room"')
        self.assertContains(list_page, reverse("admin:rooms_room_change", args=[self.room.pk]), count=1)
        self.assertContains(list_page, '<td class="field-name">Existing custom room</td>', html=True)

        response = self.client.post(reverse("admin:rooms_room_change", args=[self.room.pk]), self.data(
            name_0="Chemistry Seminar Room 110 (CH 110)",
            room_type_0="Seminar Room", building=new_building.pk, room_number="B12",
            capacity="35", size_category="small", facilities=[new_facility.pk],
        ))
        self.assertEqual(response.status_code, 302)
        self.room.refresh_from_db()
        self.assertEqual(self.room.name, "Chemistry Seminar Room 110 (CH 110)")
        self.assertEqual(self.room.code, "stable-room-url")
        self.assertEqual(self.room.room_type, "Seminar Room")
        self.assertEqual(self.room.building.campus_zone, CAMPUS_ZONES[0])
        self.assertEqual(self.room.building_id, new_building.pk)
        self.assertEqual(self.room.room_number, "B12")
        self.assertEqual(self.room.capacity, 35)
        self.assertEqual(self.room.size_category, "small")
        self.assertEqual(list(self.room.facilities.all()), [new_facility])
        self.assertEqual(Room.objects.count(), room_count)
        self.day.refresh_from_db()
        self.assertEqual(self.day.room_id, self.room.pk)
        reservation.refresh_from_db()
        self.assertEqual(reservation.room_id, self.room.pk)
        self.assertEqual(reservation.status, Reservation.Status.APPROVED)
        form = RoomAdminForm(instance=self.room)
        self.assertTrue(all(not field.disabled for field in form.fields.values()))
        self.assertEqual(form.initial["name"], self.room.name)
        response = self.client.get("/api/rooms/stable-room-url/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], self.room.name)
        self.assertEqual(response.json()["capacity"], 35)
        self.assertEqual(response.json()["facilities"], ["wifi"])

    def test_others_requires_nonblank_text_with_model_length_limits(self):
        for field, limit in (("name", 200), ("room_type", 100)):
            for value in ("", "   ", "x" * (limit + 1)):
                for instance in (None, self.room):
                    with self.subTest(field=field, value=value, editing=bool(instance)):
                        form = RoomAdminForm(instance=instance, data=self.data(**{
                            f"{field}_0": OTHER_CHOICE, f"{field}_1": value,
                        }))
                        self.assertFalse(form.is_valid())
                        self.assertIn(field, form.errors)

    def test_add_custom_name_and_type_saves_trimmed_values_and_returns_them_in_api(self):
        response = self.client.post(reverse("admin:rooms_room_add"), self.data(
            name_0=OTHER_CHOICE, name_1="  Local teaching space 217  ",
            room_type_0=OTHER_CHOICE, room_type_1="  Practical teaching room  ",
        ))
        self.assertEqual(response.status_code, 302)
        room = Room.objects.get(name="Local teaching space 217")
        self.assertEqual(room.room_type, "Practical teaching room")
        room.full_clean()
        payload = self.client.get(f"/api/rooms/{room.code}/").json()
        self.assertEqual(payload["name"], room.name)
        self.assertEqual(payload["type"], room.room_type)

    def test_existing_custom_name_and_type_reopen_as_saved_choices_and_remain_editable(self):
        form = RoomAdminForm(instance=self.room)
        for field in ("name", "room_type"):
            value = getattr(self.room, field)
            self.assertEqual(form.fields[field].widget.decompress(value), [value, ''])
        form = RoomAdminForm(instance=self.room, data=self.data(
            name_0=OTHER_CHOICE, name_1=self.room.name,
            room_type_0=OTHER_CHOICE, room_type_1=self.room.room_type, capacity=70,
        ))
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.name, "Existing custom room")
        self.assertEqual(saved.room_type, "Old room type")
        self.assertEqual(saved.code, "stable-room-url")
        self.assertEqual(saved.capacity, 70)
        self.assertEqual(self.day.room_id, saved.pk)
        form = RoomAdminForm(instance=saved, data=self.data(
            name_0=OTHER_CHOICE, name_1="Updated custom teaching room",
            room_type_0=OTHER_CHOICE, room_type_1="Updated teaching type",
        ))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().code, "stable-room-url")

    def test_selected_name_and_type_ignore_custom_text(self):
        form = RoomAdminForm(data=self.data(
            name_1="Do not use this old entry", room_type_1="Do not use this old type",
        ))
        self.assertTrue(form.is_valid(), form.errors)
        room = form.save()
        self.assertEqual(room.name, "First Bank Lecture Theatre (FBLT)")
        self.assertEqual(room.room_type, "Lecture Theatre")

    def test_invalid_dropdown_values_are_rejected(self):
        for field in ("name_0", "room_type_0", "building"):
            with self.subTest(field=field):
                form = RoomAdminForm(data=self.data(**{field: "not-in-the-catalogue"}))
                self.assertFalse(form.is_valid())

    def test_duplicate_name_and_documented_alias_cannot_create_a_second_room(self):
        for saved_name in ("first bank lecture theatre (fblt)", "FBLT"):
            self.room.name = saved_name
            self.room.save()
            form = RoomAdminForm(data=self.data())
            self.assertFalse(form.is_valid())
            self.assertIn("already exists", form.errors["name"][0])
        edit = RoomAdminForm(instance=self.room, data=self.data())
        self.assertTrue(edit.is_valid(), edit.errors)
        self.assertEqual(edit.save().code, "stable-room-url")

    def test_custom_duplicate_names_and_aliases_are_rejected(self):
        self.room.name = "First Bank Lecture Theatre (FBLT)"
        self.room.save()
        for name in (self.room.name.upper(), " FBLT "):
            form = RoomAdminForm(data=self.data(name_0=OTHER_CHOICE, name_1=name))
            self.assertFalse(form.is_valid())
            self.assertIn("already exists", form.errors["name"][0])

    def test_codes_are_distinct_for_catalogue_rooms(self):
        codes = []
        for name in ("Oduduwa Lecture Theatre I (ODLT I)", "Oduduwa Lecture Theatre II (ODLT II)"):
            form = RoomAdminForm(data=self.data(name_0=name))
            self.assertTrue(form.is_valid(), form.errors)
            codes.append(form.save().code)
        self.assertNotEqual(*codes)

    def test_search_aliases_are_rendered_and_resolve_only_documented_names(self):
        response = self.client.get(reverse("admin:rooms_room_add"))
        self.assertContains(response, 'data-search-aliases="')
        self.assertIn("ODLT 1", ROOM_ALIASES["Oduduwa Lecture Theatre I (ODLT I)"])
        self.assertEqual(room_catalogue_name("ODLT1"), "Oduduwa Lecture Theatre I (ODLT I)")
        self.assertIsNone(room_catalogue_name("HSLT"))
        self.assertIsNone(room_catalogue_name("invented room"))

    def test_submitted_room_zone_cannot_override_building(self):
        form = RoomAdminForm(data=self.data(zone=CAMPUS_ZONES[0]))
        self.assertTrue(form.is_valid(), form.errors)
        room = form.save()
        data = self.client.get(f"/api/rooms/{room.code}/").json()
        self.assertEqual(data["zone"], self.building.campus_zone)
        filtered = self.client.get("/api/rooms/", {"zone": self.building.campus_zone}).json()
        self.assertIn(room.code, [value["id"] for value in filtered])
        wrong_zone = self.client.get("/api/rooms/", {"zone": CAMPUS_ZONES[0]}).json()
        self.assertNotIn(room.code, [value["id"] for value in wrong_zone])

    def test_room_requires_building(self):
        form = RoomAdminForm(data=self.data(building=""))
        self.assertFalse(form.is_valid())
        self.assertIn("building", form.errors)
        self.assertNotIn("zone", form.fields)

    def test_type_choices_are_available_without_typing(self):
        choices = list(RoomAdminForm().fields["room_type"].widget.widgets[0].choices)
        self.assertEqual(set(dict(choices)) - {"", OTHER_CHOICE}, set(ROOM_TYPES) | {self.room.room_type})
        self.assertEqual(choices[-1][0], OTHER_CHOICE)
