from django.contrib import admin

from .models import Facility, Room


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("code",)

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "zone",
        "room_type",
        "capacity",
        "size_category",
    )

    list_filter = ("zone", "room_type", "size_category")
    search_fields = ("code", "name", "zone")
    filter_horizontal = ("facilities",)

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()

