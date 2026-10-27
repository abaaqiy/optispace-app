import csv

from django.contrib import messages
from django.contrib.admin.views.main import IncorrectLookupParameters
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_http_methods

from rooms.models import Room

from .forms import TimetableUploadForm
from .models import Course
from .services.timetable_import import (
    CSV_COLUMNS, ImportProblem, apply_import, decode_upload, preview_import, spreadsheet_cell,
)


PREVIEW_SALT = "scheduling.timetable-import.v1"
PREVIEW_MAX_AGE = 30 * 60


def csv_response(filename, columns, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # Let spreadsheet applications detect UTF-8.
    writer = csv.writer(response)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([spreadsheet_cell(value) for value in row])
    return response


class TimetableImportAdminMixin:
    change_list_template = "scheduling/admin/timetable_change_list.html"

    def has_import_permission(self, request):
        return self.has_add_permission(request) and self.has_change_permission(request)

    def get_urls(self):
        wrap = self.admin_site.admin_view
        return [
            path("import/", wrap(self.import_view), name="scheduling_timetableday_import"),
            path("export/", wrap(self.export_view), name="scheduling_timetableday_export"),
            path("csv-template/", wrap(self.template_view), name="scheduling_timetableday_template"),
            path("csv-references/", wrap(self.references_view), name="scheduling_timetableday_references"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        export_url = reverse(f"{self.admin_site.name}:scheduling_timetableday_export")
        if request.GET:
            export_url += "?" + request.GET.urlencode()
        return super().changelist_view(request, {
            **(extra_context or {}), "can_import": self.has_import_permission(request),
            "timetable_export_url": export_url,
        })

    @method_decorator(require_http_methods(["GET", "POST"]))
    def import_view(self, request):
        if not self.has_import_permission(request):
            raise PermissionDenied
        form = TimetableUploadForm()
        errors, plan, token = [], None, None
        if request.method == "POST":
            if request.POST.get("action") == "confirm":
                try:
                    payload = signing.loads(request.POST.get("preview", ""), salt=PREVIEW_SALT, max_age=PREVIEW_MAX_AGE)
                    if payload["user"] != request.user.pk:
                        raise signing.BadSignature
                    def log_entry(entry, action):
                        message = "Imported from timetable CSV." if action == "Add" else "Updated from timetable CSV."
                        log = self.log_addition if action == "Add" else self.log_change
                        log(request, entry, message)
                    counts = apply_import(payload["csv"], payload["fingerprint"], log_entry)
                    self.message_user(request, (
                        f"Timetable import complete: {counts['Add']} added, {counts['Update']} updated, "
                        f"{counts['Unchanged']} unchanged. Room availability will update automatically."
                    ), messages.SUCCESS)
                    return HttpResponseRedirect(reverse(f"{self.admin_site.name}:scheduling_timetableday_changelist"))
                except (signing.BadSignature, KeyError, TypeError):
                    errors = ["This preview has expired or is invalid. Upload the CSV again to review it."]
                except ImportProblem as error:
                    errors = error.errors
            else:
                form = TimetableUploadForm(request.POST, request.FILES)
                if form.is_valid():
                    try:
                        text = decode_upload(form.cleaned_data["csv_file"])
                        plan = preview_import(text)
                        token = signing.dumps({
                            "csv": text, "fingerprint": plan.fingerprint, "user": request.user.pk,
                        }, salt=PREVIEW_SALT, compress=True)
                    except ImportProblem as error:
                        errors = error.errors
        return TemplateResponse(request, "scheduling/admin/timetable_import.html", {
            **self.admin_site.each_context(request), "opts": self.model._meta,
            "title": "Import school timetable", "form": form, "errors": errors,
            "plan": plan, "preview_token": token,
        })

    @method_decorator(require_GET)
    def template_view(self, request):
        if not self.has_import_permission(request):
            raise PermissionDenied
        return csv_response("timetable-template.csv", CSV_COLUMNS, [])

    @method_decorator(require_GET)
    def references_view(self, request):
        if not self.has_import_permission(request):
            raise PermissionDenied
        if request.GET.get("kind") == "courses":
            return csv_response("timetable-courses.csv", ("course", "title", "department"),
                                Course.objects.order_by("code").values_list("code", "title", "department"))
        return csv_response("timetable-rooms.csv", ("room", "room_code", "building", "campus_area"),
                            Room.objects.order_by("name").values_list("name", "code", "building__name", "building__campus_zone"))

    @method_decorator(require_GET)
    def export_view(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        try:
            queryset = self.get_changelist_instance(request).queryset.select_related("room", "course")
        except IncorrectLookupParameters:
            return HttpResponseBadRequest("Invalid timetable filters. Return to Timetables and choose the filters again.")
        rows = (
            (entry.pk, entry.room.code, entry.course.code if entry.course else "", entry.date.isoformat(),
             entry.start_time.isoformat(), entry.end_time.isoformat(), entry.academic_session,
             "true" if entry.is_cancelled else "false")
            for entry in queryset.iterator()
        )
        return csv_response("timetable.csv", CSV_COLUMNS, rows)
