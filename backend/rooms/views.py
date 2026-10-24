from datetime import datetime

from django.db.models import Prefetch, Q
from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from scheduling.models import Allocation, TimetableDay

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
        published_days = TimetableDay.objects.filter(
            date=self.availability_at.date(),
            is_published=True,
        ).prefetch_related(
            Prefetch(
                "allocations",
                queryset=Allocation.objects.filter(
                    is_cancelled=False,
                ).order_by("start_time"),
                to_attr="active_allocations",
            )
        )

        return Room.objects.select_related("building").prefetch_related(
            "facilities",
            Prefetch(
                "timetable_days",
                queryset=published_days,
                to_attr="availability_days",
            ),
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["availability_at"] = self.availability_at
        return context


class RoomListView(RoomAvailabilityMixin, ListAPIView):
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        values = self.query_values
        if "zone" in values:
            queryset = queryset.filter(
                Q(zone=values["zone"])
                | Q(zone="", building__campus_zone=values["zone"])
            )
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
            # "soon" is free at the selected moment, with a lecture approaching.
            statuses = {"available", "soon"} if selected_status == "available" else {selected_status}
            data = [room for room in data if room["status"] in statuses]
        return Response(data)


class RoomDetailView(RoomAvailabilityMixin, RetrieveAPIView):
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    lookup_field = "code"


class RoomFilterOptionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        zones = set(Room.objects.values_list("zone", flat=True))
        zones.update(Building.objects.values_list("campus_zone", flat=True))
        return Response({
            "zones": sorted(zone for zone in zones if zone),
            "buildings": list(Building.objects.values("id", "name", "campus_zone")),
            "facilities": [{"code": code, "label": label} for code, label in Facility.Code.choices],
        })

