from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class OptispaceUserAdmin(UserAdmin):
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

