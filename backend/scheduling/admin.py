from django.contrib import admin

from .models import Allocation, Course, TimetableDay


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "department")
    search_fields = ("code", "title", "department")
    list_filter = ("department",)


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
    autocomplete_fields = ("room",)

    def get_readonly_fields(self, request, obj=None):
        return ("room", "date") if obj else ()


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "academic_session",
        "timetable",
        "start_time",
        "end_time",
        "is_cancelled",
    )
    list_filter = ("is_cancelled", "timetable__date", "academic_session")
    search_fields = (
        "title",
        "timetable__room__code",
        "timetable__room__name",
    )
    list_select_related = ("timetable__room", "course")
    autocomplete_fields = ("timetable", "course")

