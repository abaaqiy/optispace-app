from django.contrib.auth.forms import AdminPasswordChangeForm


class AccountPasswordResetForm(AdminPasswordChangeForm):
    """An administrator sets and confirms a password using the existing rules."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This form always sets a password. Disabling login uses Active instead.
        self.fields.pop("usable_password", None)
        self.fields["password1"].label = "New password"
        self.fields["password2"].label = "Confirm new password"
        for name in ("password1", "password2"):
            self.fields[name].required = True
