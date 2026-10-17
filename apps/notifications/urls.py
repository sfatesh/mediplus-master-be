from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationsViewSet

router = DefaultRouter()
router.register(r'notifications', NotificationsViewSet, basename='notifications')

urlpatterns = [
    path('', include(router.urls)),
]
