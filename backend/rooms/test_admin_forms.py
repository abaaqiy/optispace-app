from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
            code="stable-room-url", name="Existing custom room", zone="Existing area",
            room_type="Old room type", capacity=50, size_category="large", building=cls.building,
        )
        cls.day = TimetableDay.objects.create(
            room=cls.room, date=date(2030, 1, 5), coverage_start=time(8), coverage_end=time(18),
        )
        cls.facility = Facility.objects.create(code="projector")

    def setUp(self):
        self.client.force_login(self.admin)

    def data(self, **changes):
        data = {
            "name_0": "First Bank Lecture Theatre (FBLT)", "name_1": "",
            "room_type": "Lecture Theatre", "zone": CAMPUS_ZONES[0],
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
        self.assertEqual(len(CAMPUS_ZONES), 16)
        self.assertNotIn(OTHER_ROOM, dict(form.fields["zone"].choices))

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
        self.assertEqual(data["zone"], CAMPUS_ZONES[0])

    def test_custom_name_round_trips_and_renaming_keeps_url_and_schedule(self):
        response = self.client.post(reverse("admin:rooms_room_change", args=[self.room.pk]), self.data(
            name_0=OTHER_ROOM, name_1="  Custom OAU room  ", zone="Existing area",
            room_type="Old room type", building=self.building.pk,
        ))
        self.assertEqual(response.status_code, 302)
        self.room.refresh_from_db()
        self.assertEqual(self.room.name, "Custom OAU room")
        self.assertEqual(self.room.code, "stable-room-url")
        self.assertEqual(self.room.room_type, "Old room type")
        self.assertEqual(self.room.zone, "Existing area")
        self.assertEqual(self.day.room_id, self.room.pk)
        form = RoomAdminForm(instance=self.room)
        self.assertEqual(form.fields["name"].widget.decompress(self.room.name), [OTHER_ROOM, self.room.name])
        self.assertEqual(self.client.get("/api/rooms/stable-room-url/").status_code, 200)

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
        for field in ("name_0", "room_type", "zone"):
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

    def test_explicit_zone_wins_over_building_in_api_and_filters(self):
        form = RoomAdminForm(data=self.data(building=self.building.pk))
        self.assertTrue(form.is_valid(), form.errors)
        room = form.save()
        data = self.client.get(f"/api/rooms/{room.code}/").json()
        self.assertEqual(data["zone"], CAMPUS_ZONES[0])
        filtered = self.client.get("/api/rooms/", {"zone": CAMPUS_ZONES[0]}).json()
        self.assertIn(room.code, [value["id"] for value in filtered])
        old_zone = self.client.get("/api/rooms/", {"zone": self.building.campus_zone}).json()
        self.assertNotIn(room.code, [value["id"] for value in old_zone])
        self.assertIn(CAMPUS_ZONES[0], self.client.get("/api/rooms/filters/").json()["zones"])

    def test_blank_zone_requires_building_and_then_inherits_its_zone(self):
        form = RoomAdminForm(data=self.data(zone=""))
        self.assertFalse(form.is_valid())
        self.assertIn("zone", form.errors)
        form = RoomAdminForm(data=self.data(zone="", building=self.building.pk))
        self.assertTrue(form.is_valid(), form.errors)
        room = form.save()
        self.assertEqual(self.client.get(f"/api/rooms/{room.code}/").json()["zone"], self.building.campus_zone)

    def test_type_choices_are_available_without_typing(self):
        self.assertEqual(set(dict(RoomAdminForm().fields["room_type"].choices)) - {""}, set(ROOM_TYPES))
