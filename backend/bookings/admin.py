from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Reservation
from .services import change_reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("reference", "room", "user", "date", "start_time", "end_time", "status")
    list_filter = ("status", "date", "room")
    search_fields = ("reference", "purpose", "room__name", "user__email")
    list_select_related = ("room", "user")
    readonly_fields = tuple(field.name for field in Reservation._meta.fields)
    actions = ("approve_requests", "reject_requests", "cancel_requests")
    date_hierarchy = "date"

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def apply_action(self, request, queryset, action):
        count = 0
        for reservation in queryset:
            try:
                changed = change_reservation(reservation.reference, request.user, action)
            except ValidationError as error:
                self.message_user(request, f"{reservation.reference}: {' '.join(error.messages)}", messages.ERROR)
                continue
            self.log_change(request, changed, f"Reservation action: {action}.")
            count += 1
        if count:
            self.message_user(request, f"{count} reservation(s) updated.", messages.SUCCESS)

    @admin.action(description="Approve selected pending requests", permissions=["change"])
    def approve_requests(self, request, queryset):
        self.apply_action(request, queryset, "approve")

    @admin.action(description="Reject selected pending requests", permissions=["change"])
    def reject_requests(self, request, queryset):
        self.apply_action(request, queryset, "reject")

    @admin.action(description="Cancel selected future reservations", permissions=["change"])
    def cancel_requests(self, request, queryset):
        self.apply_action(request, queryset, "cancel")
