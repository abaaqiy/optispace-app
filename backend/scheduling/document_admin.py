"""Permission-protected upload → edit → validate → apply document workflow."""

import json
from pathlib import Path
import secrets

from django import forms
from django.contrib import messages
from django.core import signing
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_http_methods
from rooms.catalog import BUILDING_NAMES, ROOM_TYPES, ROOM_CATALOGUE, CAMPUS_ZONES
from rooms.models import Building, Facility
from rooms.forms import SearchableSelect

from .models import AcademicSemester
from .services.document_extract import MAX_DRAFT_ROWS, MAX_UPLOAD, extract_document
from .services.document_review import (
    prepare_rows,
    references,
    refresh_rows,
)
from .services.timetable_import import ImportProblem
from .services.document_plan import image_plan, apply_image
from .services.course_catalog import catalogue_coverage, catalogue_payload, handbook_file
from .services.semesters import suggested_semester

from .services.document_drafts import (
    DOCUMENT_SALT, DOCUMENT_TTL, get_draft, load_document, save_document, saved_drafts, unpack_document,
)


class DocumentUploadForm(forms.Form):
    document = forms.FileField(
        label="Lecture timetable image",
        widget=forms.ClearableFileInput(
            attrs={"accept": ".png,.jpg,.jpeg,image/png,image/jpeg"}
        ),
        help_text="PNG or JPEG, at most 10 MB. Keep all weekday and time headings visible. Lecture timetables only.",
    )
    layout = forms.ChoiceField(
        required=False,
        choices=(
            ("auto", "Detect the layout"),
            ("columns", "Weekdays across the top; Course / Venue columns"),
            ("rows", "Weekdays down the left; times across the top"),
        ),
        help_text="Usually automatic. Select a layout if a heading is difficult to read.",
    )

    def clean_document(self):
        upload = self.cleaned_data["document"]
        if upload.size > MAX_UPLOAD:
            raise forms.ValidationError("Upload a file of at most 10 MB.")
        if Path(upload.name).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise forms.ValidationError(
                "Upload a PNG or JPEG lecture timetable image. PDF is no longer supported; CSV has its own importer."
            )
        return upload


class TimetableDocumentAdminMixin:
    def get_urls(self):
        wrap = self.admin_site.admin_view
        return [
            path(
                "course-handbook/<slug:source_id>/",
                wrap(self.course_handbook),
                name="scheduling_timetableday_course_handbook",
            ),
            path(
                "import-document/",
                wrap(self.document_view),
                name="scheduling_timetableday_document",
            ),
            path(
                "document-page/<int:page>/",
                wrap(self.document_page),
                name="scheduling_timetableday_document_page",
            ),
        ] + super().get_urls()

    @method_decorator(require_GET)
    def course_handbook(self, request, source_id):
        if not self.has_import_permission(request):
            raise PermissionDenied
        stream, filename = handbook_file(source_id)
        response = FileResponse(stream, content_type='application/pdf', filename=filename)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    @method_decorator(require_GET)
    def document_page(self, request, page):
        if not self.has_import_permission(request):
            raise PermissionDenied
        try:
            _, document = load_document(request.GET.get("token", ""), request.user)
            if not 1 <= page <= len(document["pages"]):
                raise Http404
            response = HttpResponse(
                document["pages"][page - 1]["image"], content_type="image/jpeg"
            )
            response["Cache-Control"] = "private, no-store"
            return response
        except ImportProblem as error:
            raise Http404 from error

    @method_decorator(require_http_methods(["GET", "POST"]))
    def document_view(self, request):
        if not self.has_import_permission(request):
            raise PermissionDenied
        form = DocumentUploadForm()
        errors, document, token, rows, plan, preview = [], None, "", [], None, ""
        coverage_checked = False
        pending = {"courses": [], "rooms": []}
        refs = references()
        options = {
            "mode": "weekly",
            "teaching_semester": "",
            "department": "", "faculty": "", "source_version": "",
        }
        if request.method == "GET" and request.GET.get("review"):
            token = request.GET["review"]
            try:
                _, document = load_document(token, request.user)
                rows = document.get("review_rows", document["rows"])
                coverage_checked = document.get("coverage_checked", False)
                options = document.get("review_options", options).copy()
                pending = document.get("pending", pending)
            except ImportProblem as error:
                errors = error.errors
        if request.method == "POST":
            action = request.POST.get("action")
            try:
                if action == "extract":
                    form = DocumentUploadForm(request.POST, request.FILES)
                    if form.is_valid():
                        document = extract_document(
                            form.cleaned_data["document"],
                            layout=form.cleaned_data.get("layout") or "auto",
                        )
                        document["rows"] = prepare_rows(document["rows"], refs)
                        document["filename"] = form.cleaned_data["document"].name
                        metadata = document.get("metadata", {})
                        for field in ("department", "faculty", "source_version"):
                            options[field] = metadata.get(field, "")
                        options['teaching_semester'] = str(suggested_semester(metadata) or '')
                        document["review_options"] = options.copy()
                        token = save_document(document, request.user)
                        rows = document["rows"]
                elif action in {"review", "confirm", "save", "refresh"}:
                    token = request.POST.get("document_token", "")
                    payload, document = load_document(token, request.user)
                    rows = document.get("review_rows", document["rows"])
                    options = document.get("review_options", options).copy()
                    coverage_checked = document.get("coverage_checked", False)
                    pending = document.get("pending", pending)
                    if action == "confirm":
                        with transaction.atomic():
                            draft = get_draft(token, request.user, lock=True)
                            document = unpack_document(draft)
                            options = document.get('review_options', options).copy()
                            pending = document.get('pending', pending)
                            try:
                                confirmed = signing.loads(
                                    request.POST.get("preview", ""),
                                    salt=DOCUMENT_SALT + ".apply",
                                    max_age=DOCUMENT_TTL,
                                )
                                if (
                                    confirmed["user"] != request.user.pk
                                    or confirmed["document"] != payload["key"]
                                    or confirmed.get("version")
                                    != document.get("preview_version")
                                ):
                                    raise signing.BadSignature
                            except (signing.BadSignature, KeyError, TypeError) as error:
                                raise ImportProblem(
                                    "This preview is invalid or expired. Validate the reviewed rows again."
                                ) from error

                            def log(entry, action):
                                (self.log_addition if action == "Add" else self.log_change)(
                                    request,
                                    entry,
                                    "Imported from an administrator-reviewed lecture timetable image.",
                                )

                            counts = apply_image(
                                document["review_rows"], options, pending,
                                confirmed["fingerprint"], request.user, document.get("filename", "Timetable image"), log,
                            )
                            draft.delete()
                        self.message_user(
                            request,
                            f"Timetable import complete: {counts['Add']} added, {counts['Unchanged']} unchanged; {counts['courses']} courses and {counts['rooms']} rooms created. Room availability will update automatically.",
                            messages.SUCCESS,
                        )
                        return HttpResponseRedirect(
                            reverse(
                                f"{self.admin_site.name}:scheduling_timetableday_changelist"
                            )
                        )
                    options = {key: request.POST.get(key, '')[:2000] for key in (
                        'teaching_semester', 'department', 'faculty', 'source_version',
                    )}
                    options["mode"] = "weekly"
                    raw = request.POST.get("rows", "[]")
                    if len(raw) > 700_000:
                        raise ImportProblem(
                            "The review is too large. Split the document into smaller files."
                        )
                    try:
                        rows = json.loads(raw)
                    except (ValueError, TypeError) as error:
                        raise ImportProblem(
                            "Review data could not be read. Reload the document."
                        ) from error
                    if not isinstance(rows, list) or any(
                        not isinstance(row, dict) for row in rows
                    ):
                        rows = document["rows"]
                        raise ImportProblem(
                            "Review data is invalid. Reload the document."
                        )
                    if len(rows) > MAX_DRAFT_ROWS:
                        rows = document.get("review_rows", document["rows"])
                        raise ImportProblem(
                            f"Review at most {MAX_DRAFT_ROWS} rows per image."
                        )
                    document["review_rows"] = rows
                    pending_raw = request.POST.get("pending", "{\"courses\": [], \"rooms\": []}")
                    if len(pending_raw) > 300_000:
                        raise ImportProblem("Too many proposed records. Split the image into smaller sections.")
                    try:
                        pending = json.loads(pending_raw)
                    except (ValueError, TypeError) as error:
                        raise ImportProblem("Proposed courses and rooms could not be read.") from error
                    if not isinstance(pending, dict) or any(
                        not isinstance(pending.get(key, []), list) or len(pending.get(key, [])) > 300
                        or any(not isinstance(item, dict) for item in pending.get(key, []))
                        for key in ("courses", "rooms")
                    ):
                        raise ImportProblem("Invalid proposed course/room records.")
                    document["pending"] = pending
                    document["review_options"] = options
                    coverage_checked = request.POST.get("coverage_checked") == "yes"
                    document["coverage_checked"] = coverage_checked
                    document["preview_version"] = secrets.token_urlsafe(16)
                    if action == "refresh":
                        # Draft references are intentionally not saved yet.
                        draft_refs = {key: [*value, *[
                            {"value": item.get("key"), "keys": []}
                            for item in pending.get(key, [])
                        ]] for key, value in refs.items()}
                        rows = refresh_rows(rows, draft_refs)
                        document["review_rows"] = rows
                    token = save_document(document, request.user, token=token)
                    if action in {"save", "refresh"}:
                        self.message_user(
                            request,
                            "Draft saved for 24 hours."
                            + (
                                " Course and room choices refreshed; new exact matches need review."
                                if action == "refresh"
                                else ""
                            ),
                            messages.SUCCESS,
                        )
                    else:
                        if not coverage_checked:
                            raise ImportProblem(
                                "Check the full image for omitted entries and confirm the weekday/time headings before validation."
                            )
                        plan, staged, text, fingerprint = image_plan(rows, options, pending, request.user)
                        document["preview_records"] = {
                            key: [str(obj) for _, obj, _ in values] for key, values in staged.items()
                        }
                        token = save_document(document, request.user, token=token)
                        preview = signing.dumps(
                            {
                                "fingerprint": fingerprint,
                                "user": request.user.pk,
                                "document": payload["key"],
                                "version": document["preview_version"],
                            },
                            salt=DOCUMENT_SALT + ".apply",
                            compress=True,
                        )
                else:
                    raise ImportProblem(
                        "Choose Upload, Save draft, Refresh choices, Validate or Apply import."
                    )
            except ImportProblem as error:
                errors = error.errors
                if document and not rows:
                    rows = document["rows"]
        if 'teaching_semester' not in options:
            # Preserve old drafts and suggest a matching centrally saved semester.
            options['teaching_semester'] = str(suggested_semester(options) or '')
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Import lecture timetable image",
            "form": form,
            "catalog_media": SearchableSelect().media,
            "saved_drafts": saved_drafts(request.user),
            "errors": errors,
            "document": document,
            "document_token": token,
            "rows": rows,
            "references": refs,
            "pending": pending,
            "course_coverage": catalogue_coverage(),
            "creation_choices": {
                "buildings": list(Building.objects.values("id", "name", "campus_zone")),
                "building_names": BUILDING_NAMES,
                "facilities": [{"value": f.pk, "label": f.get_code_display()} for f in Facility.objects.all()],
                "room_types": ROOM_TYPES, "room_names": ROOM_CATALOGUE, "faculties": CAMPUS_ZONES,
                **catalogue_payload(lambda key: reverse(
                    f"{self.admin_site.name}:scheduling_timetableday_course_handbook", args=[key]
                )),
                "can_add_course": request.user.has_perm("scheduling.add_course"),
                "can_add_room": request.user.has_perm("rooms.add_room"),
                "can_add_building": request.user.has_perm("rooms.add_building"),
            },
            "options": options,
            "teaching_semesters": AcademicSemester.objects.all(),
            "can_manage_semesters": request.user.has_perm('scheduling.view_academicsemester')
            or request.user.has_perm('scheduling.change_academicsemester'),
            "coverage_checked": coverage_checked,
            "plan": plan,
            "preview_token": preview,
        }
        if document:
            context["pages"] = [
                {
                    "url": reverse(
                        f"{self.admin_site.name}:scheduling_timetableday_document_page",
                        args=[i + 1],
                    )
                    + "?token="
                    + token,
                    "width": page["width"],
                    "height": page["height"],
                }
                for i, page in enumerate(document["pages"])
            ]
        return TemplateResponse(
            request, "scheduling/admin/timetable_document.html", context
        )
