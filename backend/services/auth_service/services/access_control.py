from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound, ValidationError

from auth_service.models import Permission, PermissionRole, Role, Utilisateur, UtilisateurPermission
from auth_service.rbac import ROLE_PERMISSIONS, normalize_role_name

from .cache import bump_cache_version


def users_queryset():
    return Utilisateur.objects.select_related("id_role").order_by("id_utilisateur")


def roles_queryset():
    return Role.objects.order_by("id_role")


def permissions_queryset():
    return Permission.objects.order_by("id_permission")


def get_user_or_404(user_id):
    user = Utilisateur.objects.select_related("id_role").filter(id_utilisateur=user_id).first()
    if not user:
        raise NotFound("User not found")
    return user


def get_role_or_404(role_id):
    role = Role.objects.filter(id_role=role_id).first()
    if not role:
        raise NotFound("Role not found")
    return role


def get_permission_or_404(permission_id):
    permission = Permission.objects.filter(id_permission=permission_id).first()
    if not permission:
        raise NotFound("Permission not found")
    return permission


def update_user_role(user_id, role):
    user = get_user_or_404(user_id)
    _sync_fixed_role_permissions(role)
    user.id_role = role
    user.save(update_fields=["id_role", "updated_at"])
    bump_cache_version()
    return user


def list_user_permissions(user_id):
    user = get_user_or_404(user_id)
    return (
        Permission.objects.filter(
            Q(role_links__id_role=user.id_role) | Q(user_links__id_utilisateur=user)
        )
        .distinct()
        .order_by("id_permission")
    )


def user_permission_names(user):
    return list(
        Permission.objects.filter(
            Q(role_links__id_role=user.id_role) | Q(user_links__id_utilisateur=user)
        )
        .order_by("id_permission")
        .values_list("nom_permission", flat=True)
        .distinct()
    )


def list_direct_user_permissions(user_id):
    user = get_user_or_404(user_id)
    return Permission.objects.filter(user_links__id_utilisateur=user).distinct().order_by("id_permission")


def _permissions_by_ids(permission_ids):
    if not permission_ids:
        return []
    permissions = list(Permission.objects.filter(id_permission__in=permission_ids))
    if len(permissions) != len(set(permission_ids)):
        raise ValidationError({"permission_ids": ["One or more permissions do not exist."]})
    return permissions


def _permissions_by_names(permission_names):
    names = [name.strip() for name in permission_names or [] if str(name).strip()]
    if not names:
        return []
    permissions = []
    for name in names:
        permission, _ = Permission.objects.get_or_create(nom_permission=name)
        permissions.append(permission)
    return permissions


def _sync_fixed_role_permissions(role):
    role_name = normalize_role_name(role.nom_role)
    permission_names = ROLE_PERMISSIONS.get(role_name)
    if permission_names is None:
        return None
    permissions = []
    for permission_name in permission_names:
        permission, _ = Permission.objects.get_or_create(nom_permission=permission_name)
        permissions.append(permission)
    PermissionRole.objects.filter(id_role=role).delete()
    PermissionRole.objects.bulk_create(
        [PermissionRole(id_role=role, id_permission=permission) for permission in permissions],
        ignore_conflicts=True,
    )
    return permissions


@transaction.atomic
def replace_user_permissions(user_id, permission_ids=None, permission_names=None):
    user = get_user_or_404(user_id)
    permissions = _permissions_by_ids(permission_ids)
    permissions.extend(_permissions_by_names(permission_names))
    unique_permissions = {permission.id_permission: permission for permission in permissions}.values()
    UtilisateurPermission.objects.filter(id_utilisateur=user).delete()
    if unique_permissions:
        UtilisateurPermission.objects.bulk_create(
            [
                UtilisateurPermission(id_utilisateur=user, id_permission=permission)
                for permission in unique_permissions
            ],
            ignore_conflicts=True,
        )
    bump_cache_version()
    return list_user_permissions(user_id)


def add_user_permission(user_id, permission_id):
    user = get_user_or_404(user_id)
    permission = get_permission_or_404(permission_id)
    UtilisateurPermission.objects.get_or_create(id_utilisateur=user, id_permission=permission)
    bump_cache_version()


def remove_user_permission(user_id, permission_id):
    user = get_user_or_404(user_id)
    permission = get_permission_or_404(permission_id)
    deleted_count, _ = UtilisateurPermission.objects.filter(
        id_utilisateur=user,
        id_permission=permission,
    ).delete()
    if deleted_count == 0:
        raise NotFound("User-permission link not found")
    bump_cache_version()


def list_role_permissions(role_id):
    role = get_role_or_404(role_id)
    _sync_fixed_role_permissions(role)
    return Permission.objects.filter(role_links__id_role=role).distinct().order_by("id_permission")


@transaction.atomic
def replace_role_permissions(role_id, permission_ids):
    role = get_role_or_404(role_id)
    fixed_permissions = _sync_fixed_role_permissions(role)
    if fixed_permissions is not None:
        bump_cache_version()
        return Permission.objects.filter(role_links__id_role=role).distinct().order_by("id_permission")
    if permission_ids:
        permissions = list(Permission.objects.filter(id_permission__in=permission_ids))
        if len(permissions) != len(set(permission_ids)):
            raise ValidationError({"permission_ids": ["One or more permissions do not exist."]})
    else:
        permissions = []
    PermissionRole.objects.filter(id_role=role).delete()
    if permissions:
        PermissionRole.objects.bulk_create(
            [PermissionRole(id_role=role, id_permission=permission) for permission in permissions],
            ignore_conflicts=True,
        )
    bump_cache_version()
    return Permission.objects.filter(role_links__id_role=role).distinct().order_by("id_permission")


def add_role_permission(role_id, permission_id):
    role = get_role_or_404(role_id)
    if normalize_role_name(role.nom_role) in ROLE_PERMISSIONS:
        raise ValidationError({"role": ["Les permissions de ce rôle sont fixes."]})
    permission = get_permission_or_404(permission_id)
    PermissionRole.objects.get_or_create(id_role=role, id_permission=permission)
    bump_cache_version()


def remove_role_permission(role_id, permission_id):
    role = get_role_or_404(role_id)
    if normalize_role_name(role.nom_role) in ROLE_PERMISSIONS:
        raise ValidationError({"role": ["Les permissions de ce rôle sont fixes."]})
    permission = get_permission_or_404(permission_id)
    deleted_count, _ = PermissionRole.objects.filter(id_role=role, id_permission=permission).delete()
    if deleted_count == 0:
        raise NotFound("Role-permission link not found")
    bump_cache_version()
