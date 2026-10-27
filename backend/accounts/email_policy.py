from django.core.exceptions import ValidationError
from django.core.validators import validate_email


OAU_EMAIL_DOMAINS = {
    "student": "student.oauife.edu.ng",
    "lecturer": "oauife.edu.ng",
    "admin": "oauife.edu.ng",
}


def validate_oau_email(email, role):
    normalized_email = (email or "").strip().lower()
    expected_domain = OAU_EMAIL_DOMAINS.get(role)

    if expected_domain is None:
        raise ValidationError("This account has an unsupported role.")

    try:
        validate_email(normalized_email)
    except ValidationError as error:
        raise ValidationError(
            "Enter a valid email address."
        ) from error

    actual_domain = normalized_email.rsplit("@", 1)[1]

    if actual_domain != expected_domain:
        raise ValidationError(
            f"{role.title()} accounts must use an "
            f"@{expected_domain} email address."
        )

    return normalized_email


def validate_oau_account_email(user):
    role = "admin" if user.is_superuser else user.role

    return validate_oau_email(user.email, role)
