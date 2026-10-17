from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import BlogPost, Comment, HospitalStat, ContactMessage, NewsletterSubscriber
from .serializers import (
    BlogPostSerializer,
    BlogPostDetailSerializer,
    CommentSerializer,
    HospitalStatSerializer,
    ContactMessageSerializer,
    NewsletterSubscriberSerializer
)


@extend_schema_view(
    list=extend_schema(summary="List published medical blog articles"),
    retrieve=extend_schema(summary="Retrieve detailed blog article with comments by slug or ID")
)
class BlogPostViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BlogPost.objects.all().prefetch_related('comments').order_by('-created_at')
    serializer_class = BlogPostSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'
    pagination_class = None

    def get_object(self):
        lookup = self.kwargs.get(self.lookup_field)
        if lookup.isdigit():
            return get_object_or_404(BlogPost, pk=int(lookup))
        return get_object_or_404(BlogPost, slug=lookup)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BlogPostDetailSerializer
        return BlogPostSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category__iexact=category)

        # Handle offset and limit pagination if provided
        try:
            offset = int(request.query_params.get('offset', 0))
            limit = int(request.query_params.get('limit', 10))
            qs = qs[offset:offset + limit]
        except (ValueError, TypeError):
            pass

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(summary="List recent blog articles")
    @action(detail=False, methods=['get'])
    def recent(self, request):
        try:
            limit = int(request.query_params.get('limit', 3))
        except (ValueError, TypeError):
            limit = 3
        qs = BlogPost.objects.all().prefetch_related('comments').order_by('-created_at')[:limit]
        serializer = BlogPostSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(summary="List distinct blog categories with article counts")
    @action(detail=False, methods=['get'])
    def categories(self, request):
        categories = (
            BlogPost.objects.values('category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        data = [{'name': c['category'], 'count': c['count']} for c in categories]
        return Response(data)

    @extend_schema(summary="Post a reader comment on a blog article")
    @action(detail=True, methods=['post'], url_path='comments')
    def add_comment(self, request, slug=None):
        blog = self.get_object()
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(blog=blog)
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class HospitalStatsView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="Retrieve public hospital statistics (Experience, Doctors, Patients, Rooms)")
    def get(self, request):
        stats = HospitalStat.objects.all().order_by('id')
        serializer = HospitalStatSerializer(stats, many=True)
        return Response({'stats': serializer.data})


class ContactMessageCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="Submit a patient / visitor contact message")
    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        return Response(ContactMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class NewsletterSubscribeView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="Subscribe an email address to hospital newsletter")
    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'email': ['Email address is required.']}, status=status.HTTP_400_BAD_REQUEST)

        sub, _ = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={'is_active': True}
        )
        serializer = NewsletterSubscriberSerializer(sub)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

