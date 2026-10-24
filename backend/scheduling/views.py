from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from .models import Allocation
from .serializers import ScheduleSerializer


class ScheduleQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])


class ScheduleListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ScheduleSerializer
    pagination_class = None

    def get_queryset(self):
        query = ScheduleQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        selected_date = query.validated_data.get("date", timezone.localdate())
        return Allocation.objects.filter(
            timetable__is_published=True, timetable__date=selected_date,
            is_cancelled=False,
        ).select_related("timetable__room", "course").order_by(
            "start_time", "timetable__room__code", "pk",
        )
