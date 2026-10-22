from rest_framework import serializers

from scheduling.services.availability import build_availability

from .models import Room


class AvailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
    )
    time = serializers.TimeField(
        required=False,
        input_formats=["%H:%M"],
    )

    def validate(self, attrs):
        if ("date" in attrs) != ("time" in attrs):
            raise serializers.ValidationError(
                "Provide both date and time, or leave both out."
            )

        return attrs


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
        )
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        at = self.context["availability_at"]

        # These records are loaded together by the view.
        days = instance.availability_days
        timetable = days[0] if days else None

        allocations = (
            timetable.active_allocations if timetable else []
        )

        data.update(
            build_availability(
                timetable,
                allocations,
                at.time(),
            )
        )

        # Identify the moment this availability result describes.
        data["availabilityAt"] = at.isoformat()

        return data

