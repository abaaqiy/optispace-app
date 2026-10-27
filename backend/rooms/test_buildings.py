from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .catalog import BUILDING_NAMES, CAMPUS_ZONES, OTHER_BUILDING
from .forms import BuildingAdminForm
from .models import Building, Room


class BuildingAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="building-admin", email="building-admin@oauife.edu.ng", password="Building-test-572!",
        )
        cls.building = Building.objects.create(name="Existing custom building", campus_zone="Legacy campus area")
        cls.room = Room.objects.create(
            code="building-room", name="Room in building", building=cls.building,
            room_type="Classroom", capacity=40, size_category="small",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def data(self, **changes):
        return {"name_0": BUILDING_NAMES[0], "name_1": "", "campus_zone": "Faculty of Science", "_save": "Save", **changes}

    def test_catalog_has_over_thirty_unique_names_and_other_last(self):
        self.assertGreater(len(BUILDING_NAMES), 30)
        self.assertEqual(len(BUILDING_NAMES), len(set(BUILDING_NAMES)))
        field = BuildingAdminForm().fields["name"]
        choices = list(field.widget.widgets[0].choices)
        self.assertEqual(len(choices), len(BUILDING_NAMES) + 2)  # Prompt and Others.
        self.assertEqual(choices[-1][0], OTHER_BUILDING)
        self.assertIn("Mathematics Building Complex (Yellow House)", BUILDING_NAMES)
        self.assertNotIn(OTHER_BUILDING, dict(BuildingAdminForm().fields["campus_zone"].choices))

    def test_building_add_renders_search_widgets_without_duplicate_libraries(self):
        response = self.client.get(reverse("admin:rooms_building_add"))
        self.assertContains(response, 'name="name_0"')
        self.assertContains(response, 'name="campus_zone"')
        self.assertContains(response, 'Custom building name (for Others)')
        self.assertContains(response, 'rooms/catalog.js', count=1)
        self.assertContains(response, 'select2.full', count=1)
        self.assertContains(response, 'vendor/jquery/jquery', count=1)

    def test_selected_name_saves_and_ignores_old_custom_text(self):
        response = self.client.post(reverse("admin:rooms_building_add"), self.data(name_1="Old custom value"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Building.objects.filter(name=BUILDING_NAMES[0], campus_zone="Faculty of Science").exists())

    def test_custom_name_and_old_zone_round_trip(self):
        form = BuildingAdminForm(instance=self.building)
        self.assertEqual(form.fields["name"].widget.decompress(self.building.name), [OTHER_BUILDING, self.building.name])
        self.assertIn(self.building.campus_zone, dict(form.fields["campus_zone"].choices))
        form = BuildingAdminForm(instance=self.building, data=self.data(
            name_0=OTHER_BUILDING, name_1="  Renovated custom building  ", campus_zone=self.building.campus_zone,
        ))
        self.assertTrue(form.is_valid(), form.errors)
        building = form.save()
        self.assertEqual(building.name, "Renovated custom building")
        self.assertEqual(building.pk, self.building.pk)
        self.room.refresh_from_db()
        self.assertEqual(self.room.building_id, building.pk)

    def test_invalid_names_duplicates_and_zones_are_rejected(self):
        for changes in (
            {"name_0": "invented-choice"}, {"name_0": OTHER_BUILDING, "name_1": "   "},
            {"name_0": OTHER_BUILDING, "name_1": "x" * 201},
            {"name_0": OTHER_BUILDING, "name_1": self.building.name.upper()},
            {"campus_zone": ""}, {"campus_zone": "invented-zone"},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(BuildingAdminForm(data=self.data(**changes)).is_valid())

    def test_building_zone_change_updates_every_room_and_filter(self):
        second = Room.objects.create(
            code="second-room", name="Second room", building=self.building,
            room_type="Classroom", capacity=40, size_category="small",
        )
        response = self.client.post(reverse("admin:rooms_building_change", args=[self.building.pk]), self.data(
            name_0=OTHER_BUILDING, name_1=self.building.name, campus_zone=CAMPUS_ZONES[0],
        ))
        self.assertEqual(response.status_code, 302)
        for room in (self.room, second):
            payload = self.client.get(f"/api/rooms/{room.code}/").json()
            self.assertEqual(payload["zone"], CAMPUS_ZONES[0])
            self.assertEqual(payload["building"]["id"], self.building.pk)
        self.assertEqual(self.client.get("/api/rooms/", {"zone": "Legacy campus area"}).json(), [])
        self.assertEqual(len(self.client.get("/api/rooms/", {"zone": CAMPUS_ZONES[0]}).json()), 2)
        self.assertEqual(self.client.get("/api/rooms/filters/").json()["zones"], [CAMPUS_ZONES[0]])

    def test_room_building_is_required_and_protected_in_database(self):
        self.room.building = None
        with self.assertRaises(ValidationError):
            self.room.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.room.save()
        with self.assertRaises(ProtectedError):
            self.building.delete()
        with self.assertRaises(FieldDoesNotExist):
            Room._meta.get_field("zone")
