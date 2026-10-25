from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bookings.models import Reservation
from scheduling.models import TimetableDay

from .catalog import CAMPUS_ZONES, OTHER_ROOM, ROOM_NAMES, ROOM_TYPES
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
            "room_type": "Lecture Theatre", "building": self.building.pk,
            "capacity": "100", "size_category": "large", "facilities": [self.facility.pk],
            "_save": "Save",
        }
        data.update(changes)
        return data

    def test_catalogue_has_fifty_distinct_names_and_other_last(self):
        form = RoomAdminForm()
        self.assertEqual(len(ROOM_NAMES), 50)
        self.assertEqual(len(set(ROOM_NAMES)), 50)
        choices = list(form.fields["name"].widget.widgets[0].choices)
        self.assertEqual(len([value for value, _ in choices if value]), 51)
        self.assertEqual(choices[-1][0], OTHER_ROOM)
        self.assertNotIn("zone", form.fields)
        self.assertTrue(form.fields["building"].required)

    def test_add_page_hides_code_and_renders_all_dropdowns(self):
        response = self.client.get(reverse("admin:rooms_room_add"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="code"')
        self.assertContains(response, 'name="name_0"')
        self.assertContains(response, 'name="name_1"')
        self.assertContains(response, '<select name="room_type"')
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

    def test_custom_name_round_trips_and_renaming_keeps_url_and_schedule(self):
        lecturer = get_user_model().objects.create_user(
            username="room-lecturer", email="room-lecturer@oauife.edu.ng", role="lecturer",
        )
        reservation = Reservation.objects.create(
            room=self.room, user=lecturer, date=self.day.date, start_time=time(12),
            end_time=time(13), purpose="Existing reservation", status="approved",
        )
        new_building = Building.objects.create(name="Updated building", campus_zone=CAMPUS_ZONES[0])
        new_facility = Facility.objects.create(code="wifi")
        self.room.facilities.add(self.facility)
        room_count = Room.objects.count()
        list_page = self.client.get(reverse("admin:rooms_room_changelist"))
        self.assertContains(list_page, 'aria-label="Edit room: Existing custom room"')
        self.assertContains(list_page, reverse("admin:rooms_room_change", args=[self.room.pk]), count=1)
        self.assertContains(list_page, '<td class="field-name">Existing custom room</td>', html=True)

        response = self.client.post(reverse("admin:rooms_room_change", args=[self.room.pk]), self.data(
            name_0=OTHER_ROOM, name_1="  Custom OAU room  ",
            room_type="Seminar Room", building=new_building.pk, room_number="B12",
            capacity="35", size_category="small", facilities=[new_facility.pk],
        ))
        self.assertEqual(response.status_code, 302)
        self.room.refresh_from_db()
        self.assertEqual(self.room.name, "Custom OAU room")
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
        self.assertEqual(form.fields["name"].widget.decompress(self.room.name), [OTHER_ROOM, self.room.name])
        response = self.client.get("/api/rooms/stable-room-url/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], self.room.name)
        self.assertEqual(response.json()["capacity"], 35)
        self.assertEqual(response.json()["facilities"], ["wifi"])

    def test_other_requires_name_and_rejects_too_long_name(self):
        for name in ("", "   ", "a" * 201):
            with self.subTest(name_length=len(name)):
                form = RoomAdminForm(data=self.data(name_0=OTHER_ROOM, name_1=name))
                self.assertFalse(form.is_valid())
                self.assertIn("name", form.errors)

    def test_selected_name_ignores_stale_custom_text(self):
        form = RoomAdminForm(data=self.data(name_1="Do not use this old entry"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().name, "First Bank Lecture Theatre (FBLT)")

    def test_invalid_dropdown_values_are_rejected(self):
        for field in ("name_0", "room_type", "building"):
            with self.subTest(field=field):
                form = RoomAdminForm(data=self.data(**{field: "not-in-the-catalogue"}))
                self.assertFalse(form.is_valid())

    def test_duplicate_room_name_is_rejected(self):
        form = RoomAdminForm(data=self.data(name_0=OTHER_ROOM, name_1=self.room.name.upper()))
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", form.errors["name"][0])

    def test_similar_names_have_different_codes(self):
        codes = []
        for name in ("OAU Room A!", "OAU Room A?"):
            form = RoomAdminForm(data=self.data(name_0=OTHER_ROOM, name_1=name))
            self.assertTrue(form.is_valid(), form.errors)
            codes.append(form.save().code)
        self.assertNotEqual(*codes)

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
        self.assertEqual(set(dict(RoomAdminForm().fields["room_type"].choices)) - {""}, set(ROOM_TYPES))
