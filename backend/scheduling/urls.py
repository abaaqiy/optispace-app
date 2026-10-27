from django.urls import path

from .views import ScheduleListView

app_name = "scheduling"
urlpatterns = [path("", ScheduleListView.as_view(), name="schedule-list")]
