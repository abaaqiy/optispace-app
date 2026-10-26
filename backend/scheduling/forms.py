from django import forms

from .models import TimetableDay


class TimetableUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Timetable CSV",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
        help_text="CSV UTF-8, up to 1 MB and 1,000 classes. Download the template below to get started.",
    )


class TimetableAdminForm(forms.ModelForm):
    class Meta:
        model = TimetableDay
        fields = ("room", "date", "start_time", "end_time", "course", "academic_session", "is_cancelled")
        labels = {"is_cancelled": "Cancelled"}
        help_texts = {
            "start_time": "Lagos time. Only seminar rooms/halls and event halls show Reserved in the preceding 15 minutes.",
            "end_time": "The room shows Occupied from start time until end time.",
            "academic_session": "For example: 2026/2027.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].required = True
        self.fields["academic_session"].required = True
