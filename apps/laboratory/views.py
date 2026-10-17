from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import Role
from apps.common.permissions import IsStaffMember, IsLabTechnician, IsDoctor, IsPatientOwnerOrStaff
from .models import (
    LabTestCatalogue,
    LabTestParameter,
    LabOrder,
    LabOrderItem,
    LabSpecimen,
    LabResult,
)
from .serializers import (
    LabTestCatalogueSerializer,
    LabTestParameterSerializer,
    LabOrderSerializer,
    LabOrderItemSerializer,
    LabSpecimenSerializer,
    LabResultSerializer,
)
from .services import (
    create_lab_order,
    collect_specimen,
    record_test_results,
    verify_and_release_result,
    get_critical_lab_alerts,
)


class LabTestCatalogueViewSet(viewsets.ModelViewSet):
    queryset = LabTestCatalogue.objects.all().prefetch_related('parameters')
    serializer_class = LabTestCatalogueSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name', 'code', 'category']
    filterset_fields = ['category', 'specimen_type', 'is_active']


class LabOrderViewSet(viewsets.ModelViewSet):
    queryset = LabOrder.objects.all().select_related('patient', 'ordering_doctor').prefetch_related('items__lab_test', 'items__result', 'specimens')
    serializer_class = LabOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsPatientOwnerOrStaff]
    filterset_fields = ['patient', 'priority', 'status']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return LabOrder.objects.none()
        
        # Patients can only see their own lab orders
        if user.role == Role.PATIENT:
            return self.queryset.filter(patient__user=user)
        return self.queryset

    def create(self, request, *args, **kwargs):
        patient_id = request.data.get('patient_id')
        test_ids = request.data.get('test_ids', [])
        doctor_id = request.data.get('doctor_id')
        priority = request.data.get('priority', 'ROUTINE')
        indication = request.data.get('clinical_indication', '')
        encounter_id = request.data.get('encounter_id')
        admission_id = request.data.get('admission_id')

        try:
            order = create_lab_order(
                patient_id=patient_id,
                test_ids=test_ids,
                user=request.user,
                doctor_id=doctor_id,
                priority=priority,
                clinical_indication=indication,
                encounter_id=encounter_id,
                admission_id=admission_id
            )
            serializer = self.get_serializer(order)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class LabSpecimenViewSet(viewsets.ModelViewSet):
    queryset = LabSpecimen.objects.all().select_related('order__patient', 'collected_by')
    serializer_class = LabSpecimenSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]

    @action(detail=True, methods=['post'])
    def collect(self, request, pk=None):
        notes = request.data.get('notes', '')
        try:
            specimen = collect_specimen(pk, request.user, notes)
            serializer = self.get_serializer(specimen)
            return Response(serializer.data)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class LabResultViewSet(viewsets.ModelViewSet):
    queryset = LabResult.objects.all().select_related(
        'order_item__order__patient',
        'order_item__lab_test',
        'recorded_by',
        'verified_by',
        'released_by'
    ).prefetch_related('parameter_values__parameter')
    serializer_class = LabResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return LabResult.objects.none()

        # Rule: Keep unreleased results strictly inaccessible to patients!
        if user.role == Role.PATIENT:
            return self.queryset.filter(
                is_released=True,
                status='RELEASED',
                order_item__order__patient__user=user
            )

        return self.queryset

    @action(detail=False, methods=['post'], url_path='record')
    def record_values(self, request):
        order_item_id = request.data.get('order_item_id')
        parameter_values = request.data.get('parameter_values', [])
        summary_notes = request.data.get('summary_notes', '')
        correction_reason = request.data.get('correction_reason', '')

        if not order_item_id or not parameter_values:
            return Response({'detail': 'order_item_id and parameter_values are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = record_test_results(
                order_item_id=order_item_id,
                parameter_values=parameter_values,
                summary_notes=summary_notes,
                user=request.user,
                correction_reason=correction_reason
            )
            serializer = self.get_serializer(result)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except PermissionDenied as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='verify-release')
    def verify_release(self, request, pk=None):
        release_to_patient = request.data.get('release_to_patient', True)
        try:
            result = verify_and_release_result(pk, request.user, release_to_patient)
            serializer = self.get_serializer(result)
            return Response(serializer.data)
        except PermissionDenied as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='critical-alerts')
    def critical_alerts(self, request):
        alerts = get_critical_lab_alerts()
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)
