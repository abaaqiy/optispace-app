from rest_framework import serializers

from .models import Allocation


class ScheduleSerializer(serializers.ModelSerializer):
    """Keep the fields used by the existing campus schedule table."""

    refId = serializers.SerializerMethodField()
    roomId = serializers.CharField(source="timetable.room.code")
    roomName = serializers.CharField(source="timetable.room.name")
    purpose = serializers.CharField(source="title")
    date = serializers.DateField(source="timetable.date")
    timeSlot = serializers.SerializerMethodField()
    organizer = serializers.SerializerMethodField()
    staffId = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    isApproved = serializers.SerializerMethodField()

    class Meta:
        model = Allocation
        fields = (
            "refId", "roomId", "roomName", "purpose", "date", "timeSlot",
            "organizer", "staffId", "status", "isApproved",
        )
        read_only_fields = fields

    def get_refId(self, obj):
        return f"LECTURE-{obj.pk}"

    def get_timeSlot(self, obj):
        return f"{obj.start_time:%H:%M} - {obj.end_time:%H:%M}"

    def get_organizer(self, obj):
        return obj.course.department if obj.course else "Published timetable"

    def get_staffId(self, obj):
        return ""

    def get_status(self, obj):
        return "Scheduled"

    def get_isApproved(self, obj):
        return True
