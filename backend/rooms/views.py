from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from .models import Room
from .serializers import RoomSerializer


class RoomListView(ListAPIView):
    queryset = Room.objects.prefetch_related("facilities")
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]

    # Return an array, matching the frontend's current data structure.
    pagination_class = None


class RoomDetailView(RetrieveAPIView):
    queryset = Room.objects.prefetch_related("facilities")
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    lookup_field = "code"

