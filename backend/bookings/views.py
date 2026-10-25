from django.core.exceptions import ValidationError as ModelValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Reservation
from .serializers import ReservationRequestSerializer, ReservationSerializer, ReviewSerializer
from .services import change_reservation


class ReservationView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def queryset(self):
        rows = Reservation.objects.select_related("room", "user")
        return rows if self.request.user.is_superuser else rows.filter(user=self.request.user)

    def represent(self, reservation):
        return ReservationSerializer(reservation, context={"request": self.request}).data


class ReservationListView(ReservationView):
    def get(self, request):
        rows = self.queryset()
        status = request.query_params.get("status")
        if status:
            if status not in Reservation.Status.values:
                raise serializers.ValidationError({"status": "Choose pending, approved, rejected or cancelled."})
            rows = rows.filter(status=status)
        return Response(ReservationSerializer(rows, many=True, context={"request": request}).data)

    def post(self, request):
        if request.user.is_superuser:
            raise PermissionDenied("Administrators review reservations. Sign in as a student or lecturer to request a room.")
        serializer = ReservationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reservation = Reservation.objects.create(user=request.user, **serializer.validated_data)
        except ModelValidationError as error:
            raise serializers.ValidationError({"detail": " ".join(error.messages)}) from error
        return Response(self.represent(reservation), status=201)


class ReservationActionView(ReservationView):
    def post(self, request, reference, action):
        # Scope first so other users cannot discover a private request by its ID.
        get_object_or_404(self.queryset(), reference=reference)
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reservation = change_reservation(reference, request.user, action, serializer.validated_data["note"])
        except ModelValidationError as error:
            return Response({"detail": " ".join(error.messages)}, status=409)
        return Response(self.represent(reservation))
