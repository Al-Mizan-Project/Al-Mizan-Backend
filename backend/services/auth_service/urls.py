from django.urls import path

from .views import (
    AuthLoginView,
    AuthRefreshView,
    AuthLogoutView,
    AuthChangePasswordView,
    AuthForgotPasswordView,
    AuthResetPasswordView,
    UserListCreateView,
    UserRetrieveUpdateDeleteView,
    UserRoleUpdateView,
    UserPermissionsView,
    RoleListCreateView,
    RoleRetrieveUpdateDeleteView,
    PermissionListCreateView,
    PermissionRetrieveUpdateDeleteView,
    RolePermissionsView,
    RolePermissionDetailView,
)

urlpatterns = [
    path("auth/login", AuthLoginView.as_view()),
    path("auth/refresh", AuthRefreshView.as_view()),
    path("auth/logout", AuthLogoutView.as_view()),
    path("auth/change-password", AuthChangePasswordView.as_view()),
    path("auth/forgot-password", AuthForgotPasswordView.as_view()),
    path("auth/reset-password", AuthResetPasswordView.as_view()),
    path("users", UserListCreateView.as_view()),
    path("users/<int:user_id>", UserRetrieveUpdateDeleteView.as_view()),
    path("users/<int:user_id>/role", UserRoleUpdateView.as_view()),
    path("users/<int:user_id>/permissions", UserPermissionsView.as_view()),
    path("roles", RoleListCreateView.as_view()),
    path("roles/<int:role_id>", RoleRetrieveUpdateDeleteView.as_view()),
    path("permissions", PermissionListCreateView.as_view()),
    path("permissions/<int:permission_id>", PermissionRetrieveUpdateDeleteView.as_view()),
    path("roles/<int:role_id>/permissions", RolePermissionsView.as_view()),
    path("roles/<int:role_id>/permissions/<int:permission_id>", RolePermissionDetailView.as_view()),
]
