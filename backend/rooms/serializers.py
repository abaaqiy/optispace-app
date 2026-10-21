from rest_framework import serializers

from .models import Room


class RoomSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="code", read_only=True)
    type = serializers.CharField(source="room_type", read_only=True)

    sizeCategory = serializers.CharField(
        source="size_category",
        read_only=True,
    )

    facilities = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field="code",
    )

    status = serializers.SerializerMethodField()
    statusText = serializers.SerializerMethodField()
    currentSchedule = serializers.SerializerMethodField()
    nextSchedule = serializers.SerializerMethodField()
    hourlySchedule = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = (
            "id",
            "name",
            "zone",
            "type",
            "capacity",
            "sizeCategory",
            "facilities",
            "status",
            "statusText",
            "currentSchedule",
            "nextSchedule",
            "hourlySchedule",
        )
        read_only_fields = fields

    # Honest placeholders until scheduling is implemented.
    def get_status(self, obj):
        return "unknown"

    def get_statusText(self, obj):
        return "Timetable not loaded yet"

    def get_currentSchedule(self, obj):
        return None

    def get_nextSchedule(self, obj):
        return None

    def get_hourlySchedule(self, obj):
        return []

