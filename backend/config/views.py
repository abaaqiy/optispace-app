from django.conf import settings
from django.db import DatabaseError, connection
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@require_safe
def frontend(request):
    try:
        index = (settings.FRONTEND_ROOT / "index.html").open("rb")
    except FileNotFoundError:
        raise Http404("Build the frontend with npm run build before serving it.") from None
    response = FileResponse(index, content_type="text/html")
    response["Cache-Control"] = "no-store"
    return response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return Response(
            {
                "status": "error",
                "service": "Optispace API",
                "database": "unavailable",
            },
            status=503,
        )

    return Response({
        "status": "ok",
        "service": "Optispace API",
        "database": "ok",
    })

