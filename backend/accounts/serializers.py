from uuid import uuid4

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )


class UserSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "name",
            "department",
            "role",
        )
        read_only_fields = fields

    def get_name(self, user):
        return user.get_full_name() or user.username

    def get_role(self, user):
        return "admin" if user.is_superuser else user.role


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        max_length=128,
    )
    department = serializers.CharField(max_length=150)
    confirmPassword = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        max_length=128,
        error_messages={
            "required": "Please confirm your password.",
            "blank": "Please confirm your password.",
        },
    )
    role = serializers.ChoiceField(choices=User.Role.choices)

    matricNumber = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
    )
    staffId = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
    )

    def validate(self, attrs):
        if attrs["password"] != attrs["confirmPassword"]:
            raise serializers.ValidationError({
                "confirmPassword": "Passwords do not match. Please enter the same password twice.",
            })

        protected_fields = (
            "username",
            "is_staff",
            "is_superuser",
            "is_active",
            "groups",
            "user_permissions",
        )

        for field in protected_fields:
            if field in self.initial_data:
                raise serializers.ValidationError({
                    field: "This field cannot be set during public registration.",
                })

        role = attrs["role"]
        email = attrs["email"].strip().lower()

        if role == User.Role.STUDENT:
            id_field = "matricNumber"
            other_field = "staffId"
        else:
            id_field = "staffId"
            other_field = "matricNumber"

        identifier = attrs[id_field].strip().upper()

        if not identifier:
            raise serializers.ValidationError({
                id_field: "Enter your university ID.",
            })

        if attrs[other_field]:
            raise serializers.ValidationError({
                other_field: "Leave this field empty for the selected role.",
            })

        # Friendly errors before the database's uniqueness checks.
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({
                "email": "An account with this email already exists.",
            })

        if User.objects.filter(
            role=role,
            institutional_id__iexact=identifier,
        ).exists():
            raise serializers.ValidationError({
                id_field: "An account with this university ID already exists.",
            })

        first_name, _, last_name = attrs["name"].partition(" ")

        candidate = User(
            username=uuid4().hex,
            email=email,
            first_name=first_name,
            last_name=last_name,
            department=attrs["department"],
            institutional_id=identifier,
            role=role,
            is_active=(role == User.Role.STUDENT),
            is_staff=False,
            is_superuser=False,
        )

        # The model enforces the OAU email policy.
        # The password has not been hashed/assigned yet.
        try:
            candidate.full_clean(exclude=["password"])
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                error.message_dict
            ) from error

        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({
                "password": error.messages,
            }) from error

        attrs["username"] = candidate.username
        attrs["email"] = candidate.email
        attrs["first_name"] = first_name
        attrs["last_name"] = last_name
        attrs["institutional_id"] = candidate.institutional_id

        return attrs

    def create(self, validated_data):
        role = validated_data["role"]

        try:
            with transaction.atomic():
                return User.objects.create_user(
                    username=validated_data["username"],
                    email=validated_data["email"],
                    password=validated_data["password"],
                    first_name=validated_data["first_name"],
                    last_name=validated_data["last_name"],
                    department=validated_data["department"],
                    institutional_id=validated_data["institutional_id"],
                    role=role,
                    is_active=(role == User.Role.STUDENT),
                    is_staff=False,
                    is_superuser=False,
                )
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                error.message_dict
            ) from error
        except IntegrityError as error:
            raise serializers.ValidationError({
                "detail": (
                    "An account with this email or university ID "
                    "already exists."
                ),
            }) from error

