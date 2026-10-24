from django.urls import path

from .views import RoomDetailView, RoomFilterOptionsView, RoomListView


app_name = "rooms"

urlpatterns = [
    path("", RoomListView.as_view(), name="room-list"),
    path("filters/", RoomFilterOptionsView.as_view(), name="room-filters"),
    path("<slug:code>/", RoomDetailView.as_view(), name="room-detail"),
]

