from uuid import uuid4

from django import forms
from django.conf import settings
from django.utils.text import slugify

from .catalog import CAMPUS_ZONES, OTHER_ROOM, ROOM_NAMES, ROOM_TYPES
from .models import Room


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


class RoomNameWidget(forms.MultiWidget):
    template_name = "rooms/widgets/room_name.html"

    def __init__(self, attrs=None):
        choices = [("", "Select a room…")]
        choices.extend((name, name) for name in ROOM_NAMES)
        choices.append((OTHER_ROOM, "Others — enter a room name"))
        super().__init__([
            SearchableSelect(choices=choices),
            forms.TextInput(attrs={"maxlength": 200, "placeholder": "Enter the room name"}),
        ], attrs)

    def decompress(self, value):
        if not value:
            return ["", ""]
        return [value, ""] if value in ROOM_NAMES else [OTHER_ROOM, value]

    def id_for_label(self, id_):
        return f"{id_}_0" if id_ else ""

    def use_required_attribute(self, initial):
        # Only the custom-name branch is conditional; the server validates both.
        return False


class RoomNameField(forms.MultiValueField):
    widget = RoomNameWidget

    def __init__(self, **kwargs):
        super().__init__(fields=(
            forms.ChoiceField(choices=[(name, name) for name in ROOM_NAMES]
                              + [(OTHER_ROOM, "Others")]),
            forms.CharField(required=False, max_length=200),
        ), require_all_fields=False, **kwargs)

    def compress(self, values):
        if not values:
            return ""
        selected, custom = values
        if selected == OTHER_ROOM:
            if not custom:
                raise forms.ValidationError("Enter a room name when selecting Others.")
            return custom
        return selected


class RoomAdminForm(forms.ModelForm):
    name = RoomNameField(
        label="Room name",
        help_text="Search by name or abbreviation. Select Others to enter a different room.",
    )
    room_type = forms.ChoiceField(
        choices=[("", "Select a room type…")] + [(value, value) for value in ROOM_TYPES],
    )
    zone = forms.ChoiceField(
        label="Zone / campus area",
        required=False,
        choices=[("", "Select a campus area…")] + [(value, value) for value in CAMPUS_ZONES],
        widget=SearchableSelect,
        help_text="Select a campus area, or leave blank to use the selected building's zone.",
    )

    class Meta:
        model = Room
        fields = (
            "name", "room_type", "zone", "building", "room_number",
            "capacity", "size_category", "facilities",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Legacy data remains editable without silently renaming or reclassifying
        # existing rooms. It is not offered when creating unrelated rooms.
        if self.instance.pk:
            for field_name in ("zone", "room_type"):
                value = getattr(self.instance, field_name)
                field = self.fields[field_name]
                if value and value not in dict(field.choices):
                    field.choices = [*field.choices, (value, f"{value} (current value)")]

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Room.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This room already exists. Edit its existing record instead.")
        return name

    def clean(self):
        cleaned = super().clean()
        if "zone" in cleaned and not cleaned["zone"] and not cleaned.get("building"):
            self.add_error("zone", "Select a campus area or choose a building.")
        return cleaned

    def save(self, commit=True):
        room = super().save(commit=False)
        if not room.code:
            # URLs use this permanent identifier. Renaming a room never changes it.
            room.code = f"{slugify(room.name)[:17] or 'room'}-{uuid4().hex}"
        if commit:
            room.save()
            self.save_m2m()
        return room
