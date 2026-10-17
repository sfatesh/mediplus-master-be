from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    LoginView,
    ProfileView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
    AdminUserViewSet,
    RoleManagementViewSet,
    PermissionCatalogViewSet,
)

router = DefaultRouter()
router.register(r'accounts/users', AdminUserViewSet, basename='admin-user')
router.register(r'admin/users', AdminUserViewSet, basename='admin-user-alias')
router.register(r'accounts/roles', RoleManagementViewSet, basename='admin-role')
router.register(r'admin/roles', RoleManagementViewSet, basename='admin-role-alias')
router.register(r'accounts/permissions', PermissionCatalogViewSet, basename='admin-permission')
router.register(r'admin/permissions', PermissionCatalogViewSet, basename='admin-permission-alias')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', ProfileView.as_view(), name='auth-me'),
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='auth-password-reset'),
    path('auth/password-reset-confirm/', PasswordResetConfirmView.as_view(), name='auth-password-reset-confirm'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
    path('', include(router.urls)),
]
