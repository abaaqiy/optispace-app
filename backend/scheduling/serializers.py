from rest_framework import serializers

from .models import TimetableDay


class ScheduleSerializer(serializers.ModelSerializer):
    """Keep the fields used by the existing campus schedule table."""

    refId = serializers.SerializerMethodField()
    roomId = serializers.CharField(source="room.code")
    roomName = serializers.CharField(source="room.name")
    purpose = serializers.CharField(source="title")
    date = serializers.DateField()
    timeSlot = serializers.SerializerMethodField()
    organizer = serializers.SerializerMethodField()
    staffId = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    isApproved = serializers.SerializerMethodField()

    class Meta:
        model = TimetableDay
        fields = (
            "refId", "roomId", "roomName", "purpose", "date", "timeSlot",
            "organizer", "staffId", "status", "isApproved",
        )
        read_only_fields = fields

    def get_refId(self, obj):
        return f"TIMETABLE-{obj.pk}"

    def get_timeSlot(self, obj):
        return f"{obj.start_time:%H:%M} - {obj.end_time:%H:%M}"

    def get_organizer(self, obj):
        return obj.course.department if obj.course else "Timetable"

    def get_staffId(self, obj):
        return ""

    def get_status(self, obj):
        return "Cancelled" if obj.is_cancelled else "Scheduled"

    def get_isApproved(self, obj):
        return not obj.is_cancelled
