"""Permission-protected upload → edit → validate → apply document workflow."""

import json
import os
from pathlib import Path
import secrets
import tempfile

from django import forms
from django.contrib import messages
from django.core import signing
from django.core.cache.backends.filebased import FileBasedCache
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_http_methods

from .services.document_extract import MAX_DRAFT_ROWS, MAX_UPLOAD, extract_document
from .services.document_review import (
    prepare_rows,
    references,
    refresh_rows,
    reviewed_csv,
)
from .services.timetable_import import ImportProblem, apply_import, preview_import

DOCUMENT_SALT = "scheduling.image-review.v2"
DOCUMENT_TTL = 2 * 60 * 60


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


def document_cache():
    directory = Path(tempfile.gettempdir()) / f"optispace-document-review-{os.getuid()}"
    directory.mkdir(mode=0o700, exist_ok=True)
    return FileBasedCache(
        str(directory), {"TIMEOUT": DOCUMENT_TTL, "OPTIONS": {"MAX_ENTRIES": 80}}
    )


def load_document(token, user):
    try:
        payload = signing.loads(token, salt=DOCUMENT_SALT, max_age=DOCUMENT_TTL)
        if payload["user"] != user.pk:
            raise signing.BadSignature
        document = document_cache().get(payload["key"])
        if document is None:
            raise signing.BadSignature
        return payload, document
    except (signing.BadSignature, KeyError, TypeError) as error:
        raise ImportProblem(
            "This review expired or is invalid. Upload the document again. Reviews last two hours; save your draft regularly."
        ) from error


class TimetableDocumentAdminMixin:
    def get_urls(self):
        wrap = self.admin_site.admin_view
        return [
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
        refs = references()
        options = {
            "mode": "weekly",
            "academic_session": "",
            "first_date": "",
            "last_date": "",
            "exclude_dates": "",
        }
        if request.method == "GET" and request.GET.get("review"):
            token = request.GET["review"]
            try:
                _, document = load_document(token, request.user)
                rows = document.get("review_rows", document["rows"])
                coverage_checked = document.get("coverage_checked", False)
                options = document.get("review_options", options).copy()
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
                        key = secrets.token_urlsafe(32)
                        document_cache().set(key, document)
                        token = signing.dumps(
                            {"key": key, "user": request.user.pk}, salt=DOCUMENT_SALT
                        )
                        rows = document["rows"]
                elif action in {"review", "confirm", "save", "refresh"}:
                    token = request.POST.get("document_token", "")
                    payload, document = load_document(token, request.user)
                    rows = document.get("review_rows", document["rows"])
                    options = document.get("review_options", options).copy()
                    coverage_checked = document.get("coverage_checked", False)
                    if action == "confirm":
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

                        counts = apply_import(
                            confirmed["csv"], confirmed["fingerprint"], log
                        )
                        document_cache().delete(payload["key"])
                        self.message_user(
                            request,
                            f"Timetable import complete: {counts['Add']} added, {counts['Unchanged']} unchanged. Room availability will update automatically.",
                            messages.SUCCESS,
                        )
                        return HttpResponseRedirect(
                            reverse(
                                f"{self.admin_site.name}:scheduling_timetableday_changelist"
                            )
                        )
                    for key in options:
                        options[key] = request.POST.get(key, "")[:2000]
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
                    document["review_options"] = options
                    coverage_checked = request.POST.get("coverage_checked") == "yes"
                    document["coverage_checked"] = coverage_checked
                    document["preview_version"] = secrets.token_urlsafe(16)
                    if action == "refresh":
                        rows = refresh_rows(rows, refs)
                        document["review_rows"] = rows
                    document_cache().set(payload["key"], document)
                    token = signing.dumps(
                        {"key": payload["key"], "user": request.user.pk},
                        salt=DOCUMENT_SALT,
                    )
                    if action in {"save", "refresh"}:
                        self.message_user(
                            request,
                            "Draft saved for two hours."
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
                        text = reviewed_csv(rows, options, refs=refs)
                        plan = preview_import(text)
                        preview = signing.dumps(
                            {
                                "csv": text,
                                "fingerprint": plan.fingerprint,
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
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Import lecture timetable image",
            "form": form,
            "errors": errors,
            "document": document,
            "document_token": token,
            "rows": rows,
            "references": refs,
            "options": options,
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
