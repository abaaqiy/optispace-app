from rest_framework import serializers

from scheduling.services.availability import build_availability

from .models import Facility, Room


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


class RoomQuerySerializer(AvailabilityQuerySerializer):
    zone = serializers.CharField(required=False, max_length=150)
    building = serializers.IntegerField(required=False, min_value=1)
    capacity = serializers.IntegerField(required=False, min_value=1)
    category = serializers.ChoiceField(required=False, choices=["small", "large"])
    facilities = serializers.ListField(
        child=serializers.ChoiceField(choices=Facility.Code.choices), required=False,
    )
    status = serializers.ChoiceField(
        required=False, choices=["available", "occupied", "soon", "unknown"],
    )


class RoomSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="code", read_only=True)
    type = serializers.CharField(source="room_type", read_only=True)
    zone = serializers.SerializerMethodField()
    building = serializers.SerializerMethodField()
    roomNumber = serializers.CharField(source="room_number", read_only=True)

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
            "building",
            "roomNumber",
        )
        read_only_fields = fields

    def get_zone(self, instance):
        return instance.zone or (instance.building.campus_zone if instance.building else "")

    def get_building(self, instance):
        if instance.building is None:
            return None
        return {"id": instance.building_id, "name": instance.building.name}

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

