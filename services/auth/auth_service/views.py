import secrets
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Utilisateur, Role, Permission, PermissionRole
from .serializers import (
    UtilisateurSerializer,
    UtilisateurCreateSerializer,
    UtilisateurUpdateSerializer,
    LoginSerializer,
    LogoutSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    PermissionSerializer,
    RolePermissionsReplaceSerializer,
    RedisAwareTokenRefreshSerializer,
    revoke_refresh_token,
    store_password_reset_token,
    consume_password_reset_token,
)


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ready = False
        cache_ready = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_ready = cursor.fetchone()[0] == 1
        except Exception:
            db_ready = False
        try:
            probe_key = "auth:ready"
            cache.set(probe_key, "1", timeout=5)
            cache_ready = cache.get(probe_key) == "1"
        except Exception:
            cache_ready = False
        if db_ready and cache_ready:
            return Response({"status": "ready"})
        return Response({"status": "not_ready", "database": db_ready, "cache": cache_ready}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class AuthLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        try:
            user = Utilisateur.objects.get(email=email)
        except Utilisateur.DoesNotExist:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        if not check_password(password, user.password):
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


class AuthRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    serializer_class = RedisAwareTokenRefreshSerializer


class AuthLogoutView(APIView):
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_refresh = serializer.validated_data["refresh"]
        revoke_refresh_token(raw_refresh)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuthChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        old_password = serializer.validated_data["old_password"]
        new_password = serializer.validated_data["new_password"]
        if not user.check_password(old_password):
            return Response({"detail": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuthForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        payload = {"detail": "If that account exists, a reset flow has been initiated"}
        user = Utilisateur.objects.filter(email=email).first()
        if user:
            token = secrets.token_urlsafe(48)
            store_password_reset_token(token, user.id_utilisateur, timeout_seconds=900)
            if settings.DEBUG:
                payload["reset_token"] = token
        return Response(payload)


class AuthResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]
        user_id = consume_password_reset_token(token)
        if not user_id:
            return Response({"detail": "Invalid or expired reset token"}, status=status.HTTP_400_BAD_REQUEST)
        user = Utilisateur.objects.filter(id_utilisateur=user_id).first()
        if not user:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserListCreateView(ListCreateAPIView):
    queryset = Utilisateur.objects.select_related("id_role").all().order_by("id_utilisateur")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UtilisateurCreateSerializer
        return UtilisateurSerializer


class UserRetrieveUpdateDeleteView(RetrieveUpdateDestroyAPIView):
    queryset = Utilisateur.objects.select_related("id_role").all()
    lookup_field = "id_utilisateur"
    lookup_url_kwarg = "user_id"

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return UtilisateurUpdateSerializer
        return UtilisateurSerializer


class UserRoleUpdateView(APIView):
    def patch(self, request, user_id):
        user = Utilisateur.objects.filter(id_utilisateur=user_id).first()
        if not user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        role_id = request.data.get("id_role")
        if not role_id:
            return Response({"id_role": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        role = Role.objects.filter(id_role=role_id).first()
        if not role:
            return Response({"id_role": ["Invalid role."]}, status=status.HTTP_400_BAD_REQUEST)
        user.id_role = role
        user.save(update_fields=["id_role", "updated_at"])
        return Response(UtilisateurSerializer(user).data)


class UserPermissionsView(APIView):
    def get(self, request, user_id):
        user = Utilisateur.objects.filter(id_utilisateur=user_id).select_related("id_role").first()
        if not user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        permissions = Permission.objects.filter(role_links__id_role=user.id_role).distinct().order_by("id_permission")
        return Response(PermissionSerializer(permissions, many=True).data)


class RoleListCreateView(ListCreateAPIView):
    queryset = Role.objects.all().order_by("id_role")
    serializer_class = RoleSerializer


class RoleRetrieveUpdateDeleteView(RetrieveUpdateDestroyAPIView):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    lookup_field = "id_role"
    lookup_url_kwarg = "role_id"


class PermissionListCreateView(ListCreateAPIView):
    queryset = Permission.objects.all().order_by("id_permission")
    serializer_class = PermissionSerializer


class PermissionRetrieveUpdateDeleteView(RetrieveUpdateDestroyAPIView):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    lookup_field = "id_permission"
    lookup_url_kwarg = "permission_id"


class RolePermissionsView(APIView):
    def get(self, request, role_id):
        role = Role.objects.filter(id_role=role_id).first()
        if not role:
            return Response(status=status.HTTP_404_NOT_FOUND)
        permissions = Permission.objects.filter(role_links__id_role=role).distinct().order_by("id_permission")
        return Response(PermissionSerializer(permissions, many=True).data)

    def put(self, request, role_id):
        role = Role.objects.filter(id_role=role_id).first()
        if not role:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = RolePermissionsReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission_ids = serializer.validated_data["permission_ids"]
        permissions = list(Permission.objects.filter(id_permission__in=permission_ids))
        if len(permissions) != len(set(permission_ids)):
            return Response({"permission_ids": ["One or more permissions do not exist."]}, status=status.HTTP_400_BAD_REQUEST)
        PermissionRole.objects.filter(id_role=role).delete()
        PermissionRole.objects.bulk_create([
            PermissionRole(id_role=role, id_permission=permission)
            for permission in permissions
        ])
        updated = Permission.objects.filter(role_links__id_role=role).distinct().order_by("id_permission")
        return Response(PermissionSerializer(updated, many=True).data)


class RolePermissionDetailView(APIView):
    def post(self, request, role_id, permission_id):
        role = Role.objects.filter(id_role=role_id).first()
        permission = Permission.objects.filter(id_permission=permission_id).first()
        if not role or not permission:
            return Response(status=status.HTTP_404_NOT_FOUND)
        PermissionRole.objects.get_or_create(id_role=role, id_permission=permission)
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request, role_id, permission_id):
        role = Role.objects.filter(id_role=role_id).first()
        permission = Permission.objects.filter(id_permission=permission_id).first()
        if not role or not permission:
            return Response(status=status.HTTP_404_NOT_FOUND)
        deleted_count, _ = PermissionRole.objects.filter(id_role=role, id_permission=permission).delete()
        if deleted_count == 0:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
