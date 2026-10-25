from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from .models import Allocation, Course, TimetableDay


class ScheduleAdmin(admin.ModelAdmin):
    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except ValidationError as error:
            # A reservation may be approved after form validation but before
            # saving. The model's room lock catches that race; show its message.
            self.message_user(request, " ".join(error.messages), messages.ERROR)
            return HttpResponseRedirect(request.path)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "department")
    search_fields = ("code", "title", "department")
    list_filter = ("department",)


@admin.register(TimetableDay)
class TimetableDayAdmin(ScheduleAdmin):
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
class AllocationAdmin(ScheduleAdmin):
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

