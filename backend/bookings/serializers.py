from django.utils import timezone
from rest_framework import serializers

from rooms.models import Room

from .models import Reservation


class ReservationRequestSerializer(serializers.Serializer):
    roomId = serializers.SlugRelatedField(
        source="room", slug_field="code", queryset=Room.objects.all()
    )
    date = serializers.DateField(input_formats=["%Y-%m-%d"])
    startTime = serializers.TimeField(source="start_time", input_formats=["%H:%M"])
    endTime = serializers.TimeField(source="end_time", input_formats=["%H:%M"])
    purpose = serializers.CharField(max_length=200)

    def validate(self, attrs):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError(
                "Send only roomId, date, startTime, endTime and purpose. Account and approval details are assigned by the server."
            )
        return attrs


class ReviewSerializer(serializers.Serializer):
    note = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )


class ReservationSerializer(serializers.ModelSerializer):
    refId = serializers.CharField(source="reference")
    roomId = serializers.CharField(source="room.code")
    roomName = serializers.CharField(source="room.name")
    startTime = serializers.TimeField(source="start_time", format="%H:%M")
    endTime = serializers.TimeField(source="end_time", format="%H:%M")
    timeSlot = serializers.SerializerMethodField()
    organizer = serializers.SerializerMethodField()
    staffId = serializers.CharField(source="user.institutional_id")
    userRole = serializers.CharField(source="user.role")
    status = serializers.CharField(source="get_status_display")
    statusCode = serializers.CharField(source="status")
    isApproved = serializers.SerializerMethodField()
    canCancel = serializers.SerializerMethodField()
    canReview = serializers.SerializerMethodField()
    canApprove = serializers.SerializerMethodField()
    reviewNote = serializers.CharField(source="review_note")
    createdAt = serializers.DateTimeField(source="created_at")
    reviewedAt = serializers.DateTimeField(source="reviewed_at")
    cancelledAt = serializers.DateTimeField(source="cancelled_at")

    class Meta:
        model = Reservation
        fields = (
            "refId",
            "roomId",
            "roomName",
            "purpose",
            "date",
            "startTime",
            "endTime",
            "timeSlot",
            "organizer",
            "staffId",
            "userRole",
            "status",
            "statusCode",
            "isApproved",
            "canCancel",
            "canReview",
            "canApprove",
            "reviewNote",
            "createdAt",
            "reviewedAt",
            "cancelledAt",
        )
        read_only_fields = fields

    def get_timeSlot(self, obj):
        return f"{obj.start_time:%H:%M} - {obj.end_time:%H:%M}"

    def get_organizer(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_isApproved(self, obj):
        return obj.status == Reservation.Status.APPROVED

    def get_canCancel(self, obj):
        user = self.context["request"].user
        return (
            (user.is_superuser or user.pk == obj.user_id)
            and obj.status
            in (
                Reservation.Status.PENDING,
                Reservation.Status.APPROVED,
            )
            and not obj.is_archived
            and obj.ends_at > timezone.now()
        )

    def get_canReview(self, obj):
        return (
            self.context["request"].user.is_superuser
            and not obj.is_archived
            and obj.status == Reservation.Status.PENDING
        )

    def get_canApprove(self, obj):
        return self.get_canReview(obj) and obj.starts_at > timezone.now()
