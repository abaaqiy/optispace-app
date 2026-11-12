from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET

from .forms import CourseAdminForm, TimetableAdminForm
from .import_admin import TimetableImportAdminMixin
from .document_admin import TimetableDocumentAdminMixin
from .models import AcademicSemester, Course, TimetableDay
from .services.locking import lock_rooms
from .services.course_catalog import catalogue_payload, handbook_file


@admin.register(AcademicSemester)
class AcademicSemesterAdmin(admin.ModelAdmin):
    change_list_template = 'scheduling/admin/semester_change_list.html'
    change_form_template = 'scheduling/admin/semester_change_form.html'
    fields = ('academic_session', 'semester', 'first_date', 'last_date', 'exclude_dates')
    list_display = ('academic_session', 'semester', 'first_date', 'last_date')
    list_filter = ('semester',)
    search_fields = ('academic_session',)

    def get_model_perms(self, request):
        # Shared settings live under Timetables, not a third scheduling category.
        return {}


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    form = CourseAdminForm
    change_form_template = "scheduling/admin/course_change_form.html"
    list_display = ("code", "display_title", "department", "title_pending")
    search_fields = ("code", "title", "department")
    list_filter = ("title_pending", "department")

    def get_urls(self):
        return [path('course-handbook/<slug:source_id>/', self.admin_site.admin_view(self.course_handbook),
                     name='scheduling_course_handbook')] + super().get_urls()

    @method_decorator(require_GET)
    def course_handbook(self, request, source_id):
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            raise PermissionDenied
        stream, filename = handbook_file(source_id)
        response = FileResponse(stream, content_type='application/pdf', filename=filename)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        can_edit = self.has_add_permission(request) if add else self.has_change_permission(request, obj)
        if can_edit:
            context['course_suggestions'] = catalogue_payload(lambda key: reverse(
                f'{self.admin_site.name}:scheduling_course_handbook', args=[key]
            ))
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    @admin.display(description="Course title", ordering="title")
    def display_title(self, obj):
        return obj.title or "Title awaiting confirmation"


@admin.register(TimetableDay)
class TimetableDayAdmin(TimetableDocumentAdminMixin, TimetableImportAdminMixin, admin.ModelAdmin):
    form = TimetableAdminForm
    fields = ("room", "date", "start_time", "end_time", "course", "academic_session", "is_cancelled", "image_import")
    readonly_fields = ("image_import",)
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
