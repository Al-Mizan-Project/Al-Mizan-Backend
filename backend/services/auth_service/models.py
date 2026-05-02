from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
import uuid
from django.db import models


class Role(models.Model):
    id_role = models.AutoField(primary_key=True)
    nom_role = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "role"


class Permission(models.Model):
    id_permission = models.AutoField(primary_key=True)
    nom_permission = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "permission"


class PermissionRole(models.Model):
    id_role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="id_role", related_name="permission_links")
    id_permission = models.ForeignKey(Permission, on_delete=models.CASCADE, db_column="id_permission", related_name="role_links")

    class Meta:
        db_table = "Permission_role"
        constraints = [
            models.UniqueConstraint(fields=["id_role", "id_permission"], name="unique_role_permission"),
        ]


class UtilisateurManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("id_membre", 0)
        user = self.create_user(email=email, password=password, **extra_fields)
        return user


class Utilisateur(AbstractBaseUser):
    id_utilisateur = models.AutoField(primary_key=True)
    id_role = models.ForeignKey(Role, on_delete=models.PROTECT, db_column="id_role", related_name="utilisateurs")
    id_membre = models.UUIDField(null=True, blank=True)
    email = models.EmailField(unique=True, max_length=255)
    password = models.CharField(max_length=255, db_column="password_hash")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UtilisateurManager()

    class Meta:
        db_table = "utilisateurs"

    @property
    def is_staff(self):
        return False

    @property
    def is_superuser(self):
        return False
