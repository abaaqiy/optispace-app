from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from rooms.models import Building, Room
from .models import Reservation


class ReservationArchiveMigrationTests(TransactionTestCase):
    def test_retired_history_is_preserved_and_new_requests_are_not_archived(self):
        user = get_user_model().objects.create_user(
            username="archive-reader", email="archive@student.oauife.edu.ng"
        )
        building = Building.objects.create(
            name="Archive test building", campus_zone="Science"
        )
        room = Room.objects.create(
            code="archive-room",
            name="Archive room",
            building=building,
            room_type="Reading Room",
            capacity=20,
            size_category="small",
        )
        future = timezone.localdate() + timedelta(days=30)
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [
            ("bookings", "0001_initial"),
            *[node for node in latest if node[0] != "bookings"],
        ]
        try:
            executor.migrate(previous)
            historical = executor.loader.project_state(previous).apps.get_model(
                "bookings", "Reservation"
            )
            original = historical.objects.create(
                room_id=room.pk,
                user_id=user.pk,
                date=future,
                start_time=time(10),
                end_time=time(12),
                purpose="Retired record",
                status="approved",
                review_note="Old note",
            )
            MigrationExecutor(connection).migrate(latest)
            saved = Reservation.objects.get(pk=original.pk)
            self.assertTrue(saved.is_archived)
            self.assertEqual(saved.reference, original.reference)
            self.assertEqual(
                (saved.status, saved.purpose, saved.review_note),
                ("approved", "Retired record", "Old note"),
            )
            self.assertEqual((saved.room_id, saved.user_id), (room.pk, user.pk))
            new = Reservation.objects.create(
                room=room,
                user=user,
                date=future,
                start_time=time(10),
                end_time=time(12),
                purpose="New request",
            )
            self.assertFalse(new.is_archived)
        finally:
            MigrationExecutor(connection).migrate(latest)
