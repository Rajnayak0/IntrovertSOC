from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from llm import chat_modes

from apps.audit.models import record

from .models import User


def _me(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "chat_mode": chat_modes.normalize_mode(user.chat_mode),
        "is_superuser": user.is_superuser,
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Deliver a CSRF token (cookie is set too); the SPA sends it as X-CSRFToken."""
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
@csrf_exempt
def login_view(request):
    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", "") or "")
    if not username or not password:
        return Response({"detail": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
    login(request, user)
    record("login", obj=None, actor=user, metadata={"ip": request.META.get("REMOTE_ADDR", "")})
    return Response(_me(user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    actor = request.user
    logout(request)
    record("logout", obj=None, actor=actor, metadata={"ip": request.META.get("REMOTE_ADDR", "")})
    return Response({"detail": "Logged out."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(_me(request.user))


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def preferences(request):
    mode = request.data.get("chat_mode")
    if not chat_modes.is_valid_mode(mode):
        return Response(
            {"detail": f"Unknown chat_mode. Valid: {', '.join(chat_modes.MODE_REGISTRY)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = request.user
    user.chat_mode = mode
    user.save(update_fields=["chat_mode"])
    return Response(_me(user))


@api_view(["GET"])
@permission_classes([AllowAny])
def modes(request):
    """Mode switcher payload (ids, labels, tooltips)."""
    return Response({"modes": chat_modes.mode_choices(), "default": chat_modes.DEFAULT_MODE})
