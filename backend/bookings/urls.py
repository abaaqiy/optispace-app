from django.urls import path

from .views import ReservationActionView, ReservationListView

urlpatterns = [
    path("", ReservationListView.as_view(), name="reservation-list"),
    path("<str:reference>/approve/", ReservationActionView.as_view(), {"action": "approve"}, name="reservation-approve"),
    path("<str:reference>/reject/", ReservationActionView.as_view(), {"action": "reject"}, name="reservation-reject"),
    path("<str:reference>/cancel/", ReservationActionView.as_view(), {"action": "cancel"}, name="reservation-cancel"),
]
