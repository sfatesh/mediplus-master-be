from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BlogPostViewSet,
    HospitalStatsView,
    ContactMessageCreateView,
    NewsletterSubscribeView
)

router = DefaultRouter()
router.register(r'blogs', BlogPostViewSet, basename='blog')

urlpatterns = [
    path('stats/', HospitalStatsView.as_view(), name='hospital-stats'),
    path('contact/', ContactMessageCreateView.as_view(), name='contact-submit'),
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('', include(router.urls)),
]

