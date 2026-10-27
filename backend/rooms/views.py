from datetime import datetime

from django.db.models import Prefetch
from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from scheduling.models import TimetableDay
from bookings.models import Reservation

from .models import Building, Facility, Room
from .serializers import RoomQuerySerializer, RoomSerializer


class RoomAvailabilityMixin:
    @cached_property
    def query_values(self):
        query = RoomQuerySerializer(
            data=self.request.query_params,
        )
        query.is_valid(raise_exception=True)

        return query.validated_data

    @cached_property
    def availability_at(self):
        values = self.query_values
        local_timezone = timezone.get_default_timezone()

        if "date" in values:
            selected = datetime.combine(
                values["date"],
                values["time"],
            )
            return timezone.make_aware(selected, local_timezone)

        return timezone.localtime(
            timezone.now(),
            local_timezone,
        )

    def get_queryset(self):
        timetable_days = TimetableDay.objects.filter(
            date=self.availability_at.date(),
        ).select_related("course").order_by("start_time")

        return Room.objects.select_related("building").prefetch_related(
            "facilities",
            Prefetch(
                "timetable_days",
                queryset=timetable_days,
                to_attr="availability_days",
            ),
            Prefetch("reservations", queryset=Reservation.objects.filter(
                date=self.availability_at.date(), status=Reservation.Status.APPROVED,
                is_archived=False,
            ).order_by("start_time"), to_attr="availability_reservations"),
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["availability_at"] = self.availability_at
        # Consult the entire saved school timetable, independently of room,
        # capacity, campus or account filters. Cancelled rows still establish
        # that a timetable was entered for this date.
        context["has_school_timetable"] = TimetableDay.objects.filter(
            date=self.availability_at.date(),
        ).exists()
        return context


class RoomListView(RoomAvailabilityMixin, ListAPIView):
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        values = self.query_values
        if "zone" in values:
            queryset = queryset.filter(building__campus_zone=values["zone"])
        if "building" in values:
            queryset = queryset.filter(building_id=values["building"])
        if "capacity" in values:
            queryset = queryset.filter(capacity__gte=values["capacity"])
        if "category" in values:
            queryset = queryset.filter(size_category=values["category"])
        for code in set(values.get("facilities", [])):
            queryset = queryset.filter(facilities__code=code)
        return queryset.distinct()

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        selected_status = self.query_values.get("status")
        if selected_status:
            data = [room for room in data if room["status"] == selected_status]
        return Response(data)


class RoomDetailView(RoomAvailabilityMixin, RetrieveAPIView):
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    lookup_field = "code"


class RoomFilterOptionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        zones = set(Building.objects.values_list("campus_zone", flat=True))
        return Response({
            "zones": sorted(zone for zone in zones if zone),
            "buildings": list(Building.objects.values("id", "name", "campus_zone")),
            "facilities": [{"code": code, "label": label} for code, label in Facility.Code.choices],
        })

