from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from .models import TimetableDay
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
        return TimetableDay.objects.filter(
            date=selected_date,
        ).select_related("room", "course").order_by(
            "start_time", "room__code", "pk",
        )
