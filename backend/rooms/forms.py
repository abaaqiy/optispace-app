from uuid import uuid4

from django import forms
from django.conf import settings
from django.utils.text import slugify

from .catalog import BUILDING_NAMES, CAMPUS_ZONES, OTHER_ROOM, ROOM_NAMES, ROOM_TYPES
from .models import Building, Room


class SearchableSelect(forms.Select):
    def __init__(self, attrs=None, choices=()):
        super().__init__({"class": "room-catalog-select", **(attrs or {})}, choices)

    @property
    def media(self):
        # Match Django's filenames so its own autocomplete and this widget
        # share one jQuery/Select2 instance in both DEBUG and production.
        suffix = "" if settings.DEBUG else ".min"
        return forms.Media(
            css={"screen": (
                f"admin/css/vendor/select2/select2{suffix}.css",
                "admin/css/autocomplete.css",
                "rooms/catalog.css",
            )},
            js=(
                f"admin/js/vendor/jquery/jquery{suffix}.js",
                f"admin/js/vendor/select2/select2.full{suffix}.js",
                "admin/js/jquery.init.js",
                "rooms/catalog.js",
            ),
        )


class CatalogNameWidget(forms.MultiWidget):
    template_name = "rooms/widgets/room_name.html"

    def __init__(self, names, kind, attrs=None):
        self.names = names
        self.kind = kind
        choices = [("", f"Select a {kind}…")]
        choices.extend((name, name) for name in names)
        choices.append((OTHER_ROOM, f"Others — enter a {kind} name"))
        super().__init__([
            SearchableSelect(choices=choices),
            forms.TextInput(attrs={"maxlength": 200, "placeholder": f"Enter the {kind} name"}),
        ], attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["kind"] = self.kind
        return context

    def decompress(self, value):
        if not value:
            return ["", ""]
        return [value, ""] if value in self.names else [OTHER_ROOM, value]

    def id_for_label(self, id_):
        return f"{id_}_0" if id_ else ""

    def use_required_attribute(self, initial):
        # Only the custom-name branch is conditional; the server validates both.
        return False


class CatalogNameField(forms.MultiValueField):
    def __init__(self, names, kind, **kwargs):
        self.kind = kind
        super().__init__(fields=(
            forms.ChoiceField(choices=[(name, name) for name in names]
                              + [(OTHER_ROOM, "Others")]),
            forms.CharField(required=False, max_length=200),
        ), widget=CatalogNameWidget(names, kind), require_all_fields=False, **kwargs)

    def compress(self, values):
        if not values:
            return ""
        selected, custom = values
        if selected == OTHER_ROOM:
            if not custom:
                raise forms.ValidationError(f"Enter a {self.kind} name when selecting Others.")
            return custom
        return selected


class BuildingAdminForm(forms.ModelForm):
    name = CatalogNameField(
        BUILDING_NAMES, "building", label="Building name",
        help_text="Search by building name or nickname. Select Others to enter a different building.",
    )
    campus_zone = forms.ChoiceField(
        label="Zone / campus area",
        choices=[("", "Select a campus area…")] + [(value, value) for value in CAMPUS_ZONES],
        widget=SearchableSelect,
        help_text="Every room in this building uses this campus area. Changing it updates all its rooms.",
    )

    class Meta:
        model = Building
        fields = ("name", "campus_zone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        value = self.instance.campus_zone
        if self.instance.pk and value and value not in dict(self.fields["campus_zone"].choices):
            self.fields["campus_zone"].choices = [
                *self.fields["campus_zone"].choices, (value, f"{value} (current value)"),
            ]

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Building.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This building already exists. Edit its existing record instead.")
        return name


class RoomAdminForm(forms.ModelForm):
    name = CatalogNameField(
        ROOM_NAMES, "room",
        label="Room name",
        help_text="Search by name or abbreviation. Select Others to enter a different room.",
    )
    room_type = forms.ChoiceField(
        choices=[("", "Select a room type…")] + [(value, value) for value in ROOM_TYPES],
    )

    class Meta:
        model = Room
        fields = (
            "name", "room_type", "building", "room_number",
            "capacity", "size_category", "facilities",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["building"].help_text = "Choose a building. This room uses the building's zone / campus area."
        # Legacy data remains editable without silently renaming or reclassifying
        # existing rooms. It is not offered when creating unrelated rooms.
        if self.instance.pk:
            for field_name in ("room_type",):
                value = getattr(self.instance, field_name)
                field = self.fields[field_name]
                if value and value not in dict(field.choices):
                    field.choices = [*field.choices, (value, f"{value} (current value)")]

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Room.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This room already exists. Edit its existing record instead.")
        return name

    def save(self, commit=True):
        room = super().save(commit=False)
        if not room.code:
            # URLs use this permanent identifier. Renaming a room never changes it.
            room.code = f"{slugify(room.name)[:17] or 'room'}-{uuid4().hex}"
        if commit:
            room.save()
            self.save_m2m()
        return room
