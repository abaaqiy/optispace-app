from django.contrib import admin

from .forms import RoomAdminForm
from .models import Building, Facility, Room


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "campus_zone")
    list_filter = ("campus_zone",)
    search_fields = ("name", "campus_zone")


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("code",)

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    form = RoomAdminForm
    list_display = (
        "name",
        "campus_area",
        "building",
        "room_number",
        "room_type",
        "capacity",
        "size_category",
    )

    list_filter = ("zone", "building", "room_type", "size_category")
    search_fields = ("code", "name", "zone", "building__name", "room_number")
    autocomplete_fields = ("building",)
    list_select_related = ("building",)
    filter_horizontal = ("facilities",)

    @admin.display(description="Zone / campus area")
    def campus_area(self, obj):
        return obj.zone or (obj.building.campus_zone if obj.building else "")

