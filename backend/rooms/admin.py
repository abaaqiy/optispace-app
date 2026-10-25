from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .forms import BuildingAdminForm, RoomAdminForm
from .models import Building, Facility, Room


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    form = BuildingAdminForm
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
    save_on_top = True
    list_display = (
        "name",
        "campus_area",
        "building",
        "room_number",
        "room_type",
        "capacity",
        "size_category",
    )
    list_display_links = None

    def get_list_display(self, request):
        columns = super().get_list_display(request)
        if self.has_change_permission(request):
            return (*columns, "edit_room")
        return columns

    @admin.display(description="Actions")
    def edit_room(self, obj):
        url = reverse(f"{self.admin_site.name}:rooms_room_change", args=[obj.pk])
        return format_html(
            '<a href="{}" aria-label="Edit room: {}">Edit room</a>', url, obj.name,
        )

    list_filter = ("building__campus_zone", "building", "room_type", "size_category")
    search_fields = ("code", "name", "building__campus_zone", "building__name", "room_number")
    autocomplete_fields = ("building",)
    list_select_related = ("building",)
    filter_horizontal = ("facilities",)

    @admin.display(description="Zone / campus area")
    def campus_area(self, obj):
        return obj.building.campus_zone

