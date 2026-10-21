from django.contrib import admin

from .models import Allocation, TimetableDay


@admin.register(TimetableDay)
class TimetableDayAdmin(admin.ModelAdmin):
    list_display = (
        "room",
        "date",
        "coverage_start",
        "coverage_end",
        "is_published",
    )
    list_filter = ("is_published", "date")
    search_fields = ("room__code", "room__name")
    list_select_related = ("room",)
    date_hierarchy = "date"


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "timetable",
        "start_time",
        "end_time",
        "is_cancelled",
    )
    list_filter = ("is_cancelled", "timetable__date")
    search_fields = (
        "title",
        "timetable__room__code",
        "timetable__room__name",
    )
    list_select_related = ("timetable__room",)

