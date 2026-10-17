from rest_framework import viewsets, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Department, Doctor
from .serializers import DepartmentSerializer, DoctorSerializer
from apps.common.permissions import IsAdminOrReadOnly


@extend_schema_view(
    list=extend_schema(summary="List all hospital departments"),
    retrieve=extend_schema(summary="Retrieve a single department by ID"),
    create=extend_schema(summary="Create a new hospital department (Staff/Admin)"),
    update=extend_schema(summary="Update department details (Staff/Admin)"),
    partial_update=extend_schema(summary="Partial update department (Staff/Admin)"),
    destroy=extend_schema(summary="Delete/deactivate department (Staff/Admin)")
)
class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().prefetch_related('doctors')
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        # Public users see active departments; staff/admins can see all
        user = self.request.user
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return Department.objects.all().prefetch_related('doctors').order_by('name')
        return Department.objects.filter(is_active=True).prefetch_related('doctors').order_by('name')


@extend_schema_view(
    list=extend_schema(summary="List all qualified medical doctors"),
    retrieve=extend_schema(summary="Retrieve doctor details by ID"),
    create=extend_schema(summary="Create a new doctor record (Staff/Admin)"),
    update=extend_schema(summary="Update doctor profile and department (Staff/Admin)"),
    partial_update=extend_schema(summary="Partial update doctor profile (Staff/Admin)"),
    destroy=extend_schema(summary="Delete doctor record (Staff/Admin)")
)
class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all().select_related('department').order_by('name')
    serializer_class = DoctorSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['department', 'is_active']
    search_fields = ['name', 'position', 'qualification', 'bio']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        qs = Doctor.objects.all().select_related('department').order_by('name')
        user = self.request.user
        if not (user and user.is_authenticated and (user.is_staff or user.is_superuser)):
            qs = qs.filter(is_active=True)

        dept_id = self.request.query_params.get('department_id') or self.request.query_params.get('department')
        if dept_id:
            qs = qs.filter(department_id=dept_id)

        return qs
