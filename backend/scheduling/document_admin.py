"""Permission-protected upload → edit → validate → apply document workflow."""

from pathlib import Path
import secrets
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core import signing
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_http_methods
from rooms.catalog import CAMPUS_ZONES
from rooms.models import Building, Facility
from rooms.forms import SearchableSelect
from rooms.choices import building_names, room_catalogue, room_types

from .models import AcademicSemester
from .services.document_extract import MAX_UPLOAD, extract_document
from .services.document_review import (
    prepare_rows,
    references,
    refresh_rows,
)
from .services.timetable_import import ImportProblem
from .services.document_plan import image_plan, apply_image
from .services.course_catalog import catalogue_coverage, catalogue_payload, handbook_file
from .services.semesters import suggested_semester
from .services.document_state import read_review_state
from .services.part_catalogue import LEVEL_PROFILES, import_selection, part_label
from .services.document_parts import continue_after_import
from .services.document_submissions import submitted_parts

from .services.document_drafts import (
    DOCUMENT_SALT, DOCUMENT_TTL, get_draft, load_document, save_document, saved_drafts, unpack_document,
    autosave_document, save_review_document, recover_review_document, draft_token, DraftConflict,
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
            path('autosave-document/', wrap(self.autosave_view), name='scheduling_timetableday_autosave'),
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

    @method_decorator(require_http_methods(['POST']))
    def autosave_view(self, request):
        if not self.has_import_permission(request):
            raise PermissionDenied
        try:
            result = autosave_document(request.POST.get('document_token', ''), request.user, read_review_state(request.POST))
            return JsonResponse(result)
        except DraftConflict as error:
            try:
                draft = get_draft(request.POST.get('document_token', ''), request.user, metadata_only=True)
            except ImportProblem as unavailable:
                return JsonResponse({'error': str(unavailable)}, status=400)
            return JsonResponse({'error': str(error), 'latest_token': draft_token(draft)}, status=409)
        except ImportProblem as error:
            return JsonResponse({'error': str(error)}, status=400)

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
        draft_conflict = False
        latest_token = ''
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
                payload, document = load_document(token, request.user)
                token = payload['token']
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
                elif action in {"review", "confirm", "save", "refresh", "recover"}:
                    token = request.POST.get("document_token", "")
                    payload, document = load_document(token, request.user)
                    rows = document.get("review_rows", document["rows"])
                    options = document.get("review_options", options).copy()
                    coverage_checked = document.get("coverage_checked", False)
                    pending = document.get("pending", pending)
                    if action == "confirm":
                        remaining_token = None
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
                                selected_rows, selected_pending, scope = import_selection(
                                    document['review_rows'], options, pending, document.get('metadata'),
                                )
                                if confirmed.get('scope') != scope or document.get('preview_scope') != scope:
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
                                selected_rows, options, selected_pending,
                                confirmed["fingerprint"], request.user, document.get("filename", "Timetable image"), log,
                                scope=scope,
                            )
                            remaining_token = continue_after_import(draft, document, scope, counts['resolved'])
                        self.message_user(
                            request,
                            f"{part_label(scope['view'])} imported: {counts['Add']} added, {counts['Unchanged']} unchanged; {counts['courses']} courses and {counts['rooms']} rooms created. Room availability will update automatically."
                            + (' Other entries remain in this draft for review.' if remaining_token else ''),
                            messages.SUCCESS,
                        )
                        if remaining_token:
                            return HttpResponseRedirect(reverse(
                                f'{self.admin_site.name}:scheduling_timetableday_document'
                            ) + '?' + urlencode({'review': remaining_token}))
                        return HttpResponseRedirect(
                            reverse(
                                f"{self.admin_site.name}:scheduling_timetableday_changelist"
                            )
                        )
                    state = read_review_state(request.POST)
                    if action == 'recover':
                        recovered = recover_review_document(token, request.user, state)
                        self.message_user(request, 'Your edits were saved as a new draft. The previous draft is unchanged.', messages.SUCCESS)
                        return HttpResponseRedirect(reverse(
                            f'{self.admin_site.name}:scheduling_timetableday_document'
                        ) + '?' + urlencode({'review': recovered}))
                    rows, pending, options = state['review_rows'], state['pending'], state['review_options']
                    coverage_checked = state['coverage_checked']
                    if action == "refresh":
                        # Draft references are intentionally not saved yet.
                        draft_refs = {key: [*value, *[
                            {"value": item.get("key"), "keys": []}
                            for item in pending.get(key, [])
                        ]] for key, value in refs.items()}
                        rows = refresh_rows(rows, draft_refs)
                        state["review_rows"] = rows
                    try:
                        token, document = save_review_document(token, request.user, state)
                    except DraftConflict:
                        # Render the submitted edits for copying/recovery, while
                        # leaving the newer saved draft and stale token untouched.
                        document.update(state)
                        draft_conflict = True
                        latest_token = payload['token']
                        raise
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
                                "Check the selected Level / Part against the image for omitted entries and confirm its weekday/time headings before validation."
                            )
                        selected_rows, selected_pending, scope = import_selection(
                            rows, options, pending, document.get('metadata'),
                        )
                        plan, staged, text, fingerprint = image_plan(selected_rows, options, selected_pending, request.user, scope=scope)
                        document['preview_scope'] = scope
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
                                "scope": scope,
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
            "draft_conflict": draft_conflict,
            "latest_document_token": latest_token or token,
            "document": document,
            "document_token": token,
            "editor_state": document.get('editor_state', {}) if document else {},
            "rows": rows,
            "level_profiles": LEVEL_PROFILES,
            "references": refs,
            "pending": pending,
            "course_coverage": catalogue_coverage(),
            "creation_choices": {
                "buildings": list(Building.objects.values("id", "name", "campus_zone")),
                "building_names": building_names(),
                "facilities": [{"value": f.pk, "label": f.get_code_display()} for f in Facility.objects.all()],
                "room_types": room_types(), "room_names": room_catalogue(), "faculties": CAMPUS_ZONES,
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
            "import_scope_label": part_label(options.get('level_view') or 'all'),
            "submitted_parts": [],
            "selected_entry_count": len(document.get('preview_scope', {}).get('indices', [])) if plan else 0,
            "other_entry_count": sum(not row.get('skip') for row in rows)
            - len(document.get('preview_scope', {}).get('indices', [])) if plan else 0,
        }
        semester_id = str(options.get('teaching_semester', ''))
        if document and semester_id.isascii() and semester_id.isdigit() and len(semester_id) <= 18:
            selected_semester = AcademicSemester.objects.filter(pk=int(semester_id)).first()
            if selected_semester:
                context['submitted_parts'] = submitted_parts({**options, 'academic_session': selected_semester.academic_session,
                                                             'semester': selected_semester.semester})
                context['submission_department'] = options.get('department', '')
                context['submission_semester'] = str(selected_semester)
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
