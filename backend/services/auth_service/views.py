from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView
from .services.access_control import user_permission_names
from .models import Utilisateur
from .permissions import AuthServicePermission
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    PermissionSerializer,
    RedisAwareTokenRefreshSerializer,
    ResetPasswordSerializer,
    RolePermissionsReplaceSerializer,
    RoleSerializer,
    UserRoleUpdateSerializer,
    UtilisateurCreateSerializer,
    UtilisateurSerializer,
    UtilisateurUpdateSerializer,
)
from .services.access_control import (
    add_role_permission,
    list_role_permissions,
    list_user_permissions,
    permissions_queryset,
    remove_role_permission,
    replace_role_permissions,
    roles_queryset,
    update_user_role,
    users_queryset,
)
from .services.authentication import (
    authenticate_user,
    change_password,
    complete_password_reset,
    initiate_password_reset,
    logout_user,
)
from .services.cache import bump_cache_version, read_cached, write_cached
from .services.health import check_readiness


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ready, cache_ready = check_readiness("auth")
        if db_ready and cache_ready:
            return Response({"status": "ready"})
        return Response(
            {"status": "not_ready", "database": db_ready, "cache": cache_ready},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class AuthLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = authenticate_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return Response(payload)


class AuthRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    serializer_class = RedisAwareTokenRefreshSerializer


class AuthLogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logout_user(serializer.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuthChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuthForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_password_reset"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = initiate_password_reset(serializer.validated_data["email"])
        return Response(payload)


class AuthResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_password_reset"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complete_password_reset(
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CachedListMixin:
    cache_namespace = ""

    def list(self, request, *args, **kwargs):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached(self.cache_namespace, "list", query_string)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            write_cached(response.data, self.cache_namespace, "list", query_string)
        return response


class CachedRetrieveMixin:
    cache_namespace = ""

    def retrieve(self, request, *args, **kwargs):
        identifier = str(kwargs.get(self.lookup_url_kwarg or self.lookup_field))
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached(self.cache_namespace, identifier, query_string)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            write_cached(response.data, self.cache_namespace, identifier, query_string)
        return response


class UserListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "users"
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "GET": ("users.read",),
        "POST": ("users.write",),
    }

    def get_queryset(self):
        return users_queryset()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UtilisateurCreateSerializer
        return UtilisateurSerializer

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class UserRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "users"
    lookup_field = "id_utilisateur"
    lookup_url_kwarg = "user_id"
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "GET": ("users.read",),
        "PATCH": ("users.write",),
        "PUT": ("users.write",),
        "DELETE": ("users.write",),
    }

    def get_queryset(self):
        return users_queryset()

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return UtilisateurUpdateSerializer
        return UtilisateurSerializer

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class UserRoleUpdateView(APIView):
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "PATCH": ("users.write",),
    }

    def patch(self, request, user_id):
        serializer = UserRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = update_user_role(user_id=user_id, role=serializer.validated_data["id_role"])
        return Response(UtilisateurSerializer(user).data)


class UserPermissionsView(APIView):
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "GET": ("users.read",),
    }

    def get(self, request, user_id):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("users-permissions", str(user_id), query_string)
        if cached is not None:
            return Response(cached)
        permissions = list_user_permissions(user_id)
        payload = PermissionSerializer(permissions, many=True).data
        write_cached(payload, "users-permissions", str(user_id), query_string)
        return Response(payload)


class RoleListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "roles"
    serializer_class = RoleSerializer
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "GET": ("roles.read",),
        "POST": ("roles.write",),
    }

    def get_queryset(self):
        return roles_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class RoleRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "roles"
    serializer_class = RoleSerializer
    lookup_field = "id_role"
    lookup_url_kwarg = "role_id"
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "GET": ("roles.read",),
        "PATCH": ("roles.write",),
        "PUT": ("roles.write",),
        "DELETE": ("roles.write",),
    }

    def get_queryset(self):
        return roles_queryset()

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class PermissionListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "permissions"
    serializer_class = PermissionSerializer
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "GET": ("permissions.read",),
        "POST": ("permissions.write",),
    }

    def get_queryset(self):
        return permissions_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class PermissionRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "permissions"
    serializer_class = PermissionSerializer
    lookup_field = "id_permission"
    lookup_url_kwarg = "permission_id"
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "GET": ("permissions.read",),
        "PATCH": ("permissions.write",),
        "PUT": ("permissions.write",),
        "DELETE": ("permissions.write",),
    }

    def get_queryset(self):
        return permissions_queryset()

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class RolePermissionsView(APIView):
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "GET": ("roles.read",),
        "PUT": ("roles.write",),
    }

    def get(self, request, role_id):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("roles-permissions", str(role_id), query_string)
        if cached is not None:
            return Response(cached)
        permissions = list_role_permissions(role_id)
        payload = PermissionSerializer(permissions, many=True).data
        write_cached(payload, "roles-permissions", str(role_id), query_string)
        return Response(payload)

    def put(self, request, role_id):
        serializer = RolePermissionsReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = replace_role_permissions(
            role_id=role_id,
            permission_ids=serializer.validated_data["permission_ids"],
        )
        return Response(PermissionSerializer(updated, many=True).data)


class RolePermissionDetailView(APIView):
    permission_classes = [AuthServicePermission]
    required_permissions = {
        "POST": ("roles.write",),
        "DELETE": ("roles.write",),
    }

    def post(self, request, role_id, permission_id):
        add_role_permission(role_id=role_id, permission_id=permission_id)
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request, role_id, permission_id):
        remove_role_permission(role_id=role_id, permission_id=permission_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

class InternalRegisterActeurView(APIView):
    """ POST /internal/users/register """
    # Idéalement, protéger par un Token de service interne (ex: X-Internal-Service-Token)
    permission_classes = [] 

    def post(self, request):
        serializer = InternalActeurRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Utilisateur créé", "id_utilisateur": user.id_utilisateur}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InternalSearchUsersView(APIView):
    """ GET /internal/users/search/?membres_ids=uuid1,uuid2 """
    permission_classes = []

    def get(self, request):
        membres_ids_str = request.query_params.get('membres_ids', '')
        if not membres_ids_str:
            return Response([], status=status.HTTP_200_OK)

        ids_list = membres_ids_str.split(',')
        users = Utilisateur.objects.filter(id_membre__in=ids_list).select_related('id_role')
        
        result = []
        for user in users:
            result.append({
                "id_membre": str(user.id_membre),
                "email": user.email,
                "is_active": user.is_active,
                "role": user.id_role.nom_role if user.id_role else None,
                "permissions": user_permission_names(user) # Utilise votre fonction existante !
            })
            
        return Response(result, status=status.HTTP_200_OK)
