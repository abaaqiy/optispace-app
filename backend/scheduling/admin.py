from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from .forms import TimetableAdminForm
from .models import Course, TimetableDay
from .services.locking import lock_rooms


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "department")
    search_fields = ("code", "title", "department")
    list_filter = ("department",)


@admin.register(TimetableDay)
class TimetableDayAdmin(admin.ModelAdmin):
    form = TimetableAdminForm
    fields = ("room", "date", "start_time", "end_time", "course", "academic_session", "is_cancelled")
    save_on_top = True
    list_display = ("room", "date", "start_time", "end_time", "course", "academic_session", "is_cancelled")
    list_filter = ("date", "academic_session", "is_cancelled")
    search_fields = ("room__code", "room__name", "course__code", "course__title")
    list_select_related = ("room", "course")
    date_hierarchy = "date"
    autocomplete_fields = ("room", "course")

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method != "POST":
            return super().changeform_view(request, object_id, form_url, extra_context)
        room_ids = []
        if object_id and object_id.isdigit():
            room_ids = list(TimetableDay.objects.filter(pk=object_id).values_list("room_id", flat=True))
        if request.POST.get("room", "").isdigit():
            room_ids.append(int(request.POST["room"]))
        try:
            with lock_rooms(room_ids):
                return super().changeform_view(request, object_id, form_url, extra_context)
        except ValidationError as error:
            self.message_user(request, " ".join(error.messages), messages.ERROR)
            return HttpResponseRedirect(request.path)
