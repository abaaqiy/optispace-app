from datetime import datetime

from django.db.models import Prefetch
from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from scheduling.models import Allocation, TimetableDay

from .models import Room
from .serializers import AvailabilityQuerySerializer, RoomSerializer


class RoomAvailabilityMixin:
    @cached_property
    def availability_at(self):
        query = AvailabilityQuerySerializer(
            data=self.request.query_params,
        )
        query.is_valid(raise_exception=True)

        values = query.validated_data
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

        return Room.objects.prefetch_related(
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


class RoomDetailView(RoomAvailabilityMixin, RetrieveAPIView):
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    lookup_field = "code"

