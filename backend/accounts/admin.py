from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError

from .models import User


@admin.register(User)
class OptispaceUserAdmin(UserAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "account_role",
        "account_active",
        "admin_access",
    )

    # Open an account by clicking its email instead of its generated username.
    list_display_links = ("email",)

    list_filter = (
        "role",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "email",
        "username",
        "first_name",
        "last_name",
        "institutional_id",
    )

    ordering = ("email",)

    fieldsets = UserAdmin.fieldsets + (
        ("Optispace", {
            "fields": (
                "role",
                "department",
                "institutional_id",
            ),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Optispace", {
            "fields": (
                "email",
                "first_name",
                "last_name",
                "role",
                "department",
                "institutional_id",
            ),
        }),
    )

    actions = ["approve_lecturers"]

    @admin.display(description="Account role", ordering="role")
    def account_role(self, obj):
        if obj.is_superuser:
            return "Administrator"

        return obj.get_role_display()

    @admin.display(
        boolean=True,
        description="Active — can sign in",
        ordering="is_active",
    )
    def account_active(self, obj):
        return obj.is_active

    @admin.display(
        boolean=True,
        description="Django admin access",
        ordering="is_staff",
    )
    def admin_access(self, obj):
        return obj.is_staff

    def has_approve_permission(self, request):
        # The approval action is available to superuser administrators.
        return request.user.is_superuser

    @admin.action(
        description="Approve selected lecturer accounts",
        permissions=["approve"],
    )
    def approve_lecturers(self, request, queryset):
        eligible_accounts = queryset.filter(
            role=User.Role.LECTURER,
            is_active=False,
            is_staff=False,
            is_superuser=False,
        )

        approved = 0

        for account in eligible_accounts:
            account.is_active = True

            try:
                # Normal save preserves our model's account validation.
                account.save(update_fields=["is_active"])
            except ValidationError as error:
                self.message_user(
                    request,
                    f"{account.email}: {' '.join(error.messages)}",
                    level=messages.ERROR,
                )
                continue

            self.log_change(
                request,
                account,
                "Lecturer account verified and activated.",
            )
            approved += 1

        if approved:
            self.message_user(
                request,
                (
                    f"{approved} lecturer account(s) approved. "
                    "No administrator permissions were added."
                ),
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                (
                    "No accounts were approved. Select inactive lecturer "
                    "accounts without administrator permissions."
                ),
                level=messages.WARNING,
            )

