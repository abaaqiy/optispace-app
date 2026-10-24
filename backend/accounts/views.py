from django.contrib.auth import (
    authenticate,
    login as django_login,
    logout as django_logout,
)
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)


class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "csrfToken": get_token(request),
        })


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        requires_approval = user.role == User.Role.LECTURER

        if requires_approval:
            message = (
                "Account created. An administrator must verify and "
                "activate your lecturer account before you can sign in."
            )
        else:
            message = "Account created. You can now sign in."

        return Response(
            {
                "detail": message,
                "user": UserSerializer(user).data,
                "requiresApproval": requires_approval,
            },
            status=201,
        )


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            account = User.objects.get(email__iexact=email)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return Response(
                {"detail": "Invalid email or password."},
                status=401,
            )

        # Django verifies the password and rejects inactive accounts.
        user = authenticate(
            request=request,
            username=account.username,
            password=password,
        )

        if user is None:
            # Only explain activation after verifying the supplied password.
            if not account.is_active and account.check_password(password):
                if account.role == User.Role.LECTURER:
                    detail = (
                        "Your lecturer account has not been activated. "
                        "Please wait for an administrator to approve it before signing in."
                    )
                else:
                    detail = "Your account is inactive. Please contact an administrator."
                return Response({"detail": detail}, status=403)
            return Response(
                {"detail": "Invalid email or password."},
                status=401,
            )

        django_login(request, user)

        return Response({
            "user": UserSerializer(user).data,
            "csrfToken": get_token(request),
        })


class MeView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "user": UserSerializer(request.user).data,
        })


class LogoutView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        django_logout(request)

        return Response({
            "detail": "Signed out.",
        })

