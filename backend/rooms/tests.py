from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from .models import Facility, Room


class RoomTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.room = Room.objects.create(
            code="room-1",
            name="Oduduwa Lecture Theatre (ODLT)",
            zone="Faculty of Computing & Engineering",
            room_type="Tiered Amphitheatre",
            capacity=1000,
            size_category="large",
        )

        wifi = Facility.objects.create(code="wifi")
        cls.room.facilities.add(wifi)

    def test_room_list_is_public_and_matches_frontend_fields(self):
        response = self.client.get("/api/rooms/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        room = response.data[0]
        self.assertEqual(room["id"], "room-1")
        self.assertEqual(room["type"], "Tiered Amphitheatre")
        self.assertEqual(room["sizeCategory"], "large")
        self.assertEqual(room["facilities"], ["wifi"])
        self.assertEqual(room["status"], "unknown")
        self.assertEqual(room["hourlySchedule"], [])

    def test_room_detail(self):
        response = self.client.get("/api/rooms/room-1/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], "room-1")

    def test_missing_room_returns_404(self):
        response = self.client.get("/api/rooms/not-a-room/")

        self.assertEqual(response.status_code, 404)

    def test_api_does_not_allow_writes(self):
        requests = [
            ("post", "/api/rooms/"),
            ("put", "/api/rooms/room-1/"),
            ("patch", "/api/rooms/room-1/"),
            ("delete", "/api/rooms/room-1/"),
        ]

        for method, url in requests:
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    url,
                    {},
                    format="json",
                )
                self.assertEqual(response.status_code, 405)

    def test_capacity_must_be_positive(self):
        self.room.capacity = 0

        with self.assertRaises(ValidationError):
            self.room.full_clean()

