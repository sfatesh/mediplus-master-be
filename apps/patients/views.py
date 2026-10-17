from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema_view, extend_schema
from .models import Patient, PatientConsent
from .serializers import PatientSerializer, PatientConsentSerializer, PatientDuplicateCheckSerializer
from apps.accounts.models import Role
from apps.common.permissions import IsPatientOwnerOrStaff, IsStaffMember
from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.audit.services import AuditService


@extend_schema_view(
    list=extend_schema(summary="List hospital patients (Staff view all, Patients view own)"),
    create=extend_schema(summary="Create a new patient record (Hospital staff only)"),
    retrieve=extend_schema(summary="Retrieve patient record by ID (Isolated per owner/staff)"),
    update=extend_schema(summary="Update patient record"),
    partial_update=extend_schema(summary="Partial update patient record")
)
class PatientViewSet(viewsets.ModelViewSet):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated, IsPatientOwnerOrStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['gender', 'blood_group', 'is_active', 'city']
    search_fields = [
        'medical_record_number',
        'first_name',
        'last_name',
        'phone',
        'email',
        'guardian_name',
        'emergency_contact_name'
    ]
    ordering_fields = ['created_at', 'last_name', 'medical_record_number', 'date_of_birth']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Patient.objects.none()

        # Hospital staff can access the complete patient database
        if user.is_hospital_staff or user.is_superuser:
            return Patient.objects.all().prefetch_related('consents')

        # Patients are strictly isolated to their own records
        if user.role == Role.PATIENT:
            return Patient.objects.filter(user=user).prefetch_related('consents')

        return Patient.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.is_hospital_staff or user.is_superuser):
            AuditService.log(
                action='UNAUTHORIZED_PATIENT_CREATION_ATTEMPT',
                request=self.request,
                status='DENIED'
            )
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only hospital staff can register new patient records directly.")

        patient = serializer.save()
        AuditService.log(
            action='PATIENT_RECORD_CREATED',
            request=self.request,
            resource_type='Patient',
            resource_id=patient.id,
            details={
                'mrn': patient.medical_record_number,
                'full_name': patient.full_name,
                'phone': patient.phone
            }
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        AuditService.log(
            action='PATIENT_RECORD_VIEW',
            request=request,
            resource_type='Patient',
            resource_id=instance.id,
            details={'mrn': instance.medical_record_number}
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_update(self, serializer):
        instance = self.get_object()
        # Capture old values for auditable diff
        tracked_fields = [
            'first_name', 'last_name', 'date_of_birth', 'gender', 'blood_group',
            'phone', 'email', 'address', 'city', 'postal_code',
            'emergency_contact_name', 'emergency_contact_phone',
            'guardian_name', 'guardian_relationship', 'guardian_phone',
            'allergies', 'medical_history', 'is_active'
        ]
        old_data = {f: str(getattr(instance, f, '')) for f in tracked_fields}

        patient = serializer.save()

        # Compute diff
        diff = {}
        for f in tracked_fields:
            new_val = str(getattr(patient, f, ''))
            if old_data.get(f) != new_val:
                diff[f] = {'old': old_data.get(f), 'new': new_val}

        AuditService.log(
            action='PATIENT_RECORD_UPDATED',
            request=self.request,
            resource_type='Patient',
            resource_id=patient.id,
            details={
                'mrn': patient.medical_record_number,
                'changes': diff
            }
        )

    def destroy(self, request, *args, **kwargs):
        if not (request.user.is_admin or request.user.has_app_permission('patients.delete')):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only administrators can deactivate patient records.")
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        # Soft delete
        instance.is_active = False
        instance.save()
        AuditService.log(
            action='PATIENT_RECORD_DEACTIVATED',
            request=self.request,
            resource_type='Patient',
            resource_id=instance.id,
            details={'mrn': instance.medical_record_number}
        )

    @extend_schema(summary="Get current authenticated patient's own profile")
    @action(detail=False, methods=['get'], url_path='me')
    def my_profile(self, request):
        if request.user.role != Role.PATIENT:
            return Response(
                {'error': 'Current user is not a registered patient.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        patient = Patient.objects.filter(user=request.user).prefetch_related('consents').first()
        if not patient:
            return Response(
                {'error': 'Patient record not found for this account.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(patient)
        return Response(serializer.data)

    @extend_schema(
        summary="Check for potential duplicate patient records",
        request=PatientDuplicateCheckSerializer
    )
    @action(detail=False, methods=['post'], url_path='check-duplicate', permission_classes=[permissions.IsAuthenticated, IsStaffMember])
    def check_duplicate(self, request):
        serializer = PatientDuplicateCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        dob = data.get('date_of_birth')

        qs = Patient.objects.filter(is_active=True)
        matches = []

        if email:
            for p in qs.filter(email__iexact=email):
                matches.append({'id': p.id, 'mrn': p.medical_record_number, 'name': p.full_name, 'reason': 'Matching email'})

        if phone and dob:
            for p in qs.filter(phone=phone, date_of_birth=dob):
                if not any(m['id'] == p.id for m in matches):
                    matches.append({'id': p.id, 'mrn': p.medical_record_number, 'name': p.full_name, 'reason': 'Matching phone & Date of Birth'})

        if first_name and last_name and dob:
            for p in qs.filter(first_name__iexact=first_name, last_name__iexact=last_name, date_of_birth=dob):
                if not any(m['id'] == p.id for m in matches):
                    matches.append({'id': p.id, 'mrn': p.medical_record_number, 'name': p.full_name, 'reason': 'Matching full name & Date of Birth'})

        return Response({
            'is_duplicate': len(matches) > 0,
            'match_count': len(matches),
            'matches': matches
        })

    @extend_schema(summary="Get audit change history for a patient record", responses={200: AuditLogSerializer(many=True)})
    @action(detail=True, methods=['get'], url_path='audit-logs', permission_classes=[permissions.IsAuthenticated, IsStaffMember])
    def audit_logs(self, request, pk=None):
        patient = self.get_object()
        logs = AuditLog.objects.filter(
            resource_type='Patient',
            resource_id=str(patient.id)
        ).select_related('user').order_by('-created_at')[:50]
        return Response(AuditLogSerializer(logs, many=True).data)

    @extend_schema(
        summary="Record patient consent",
        request=PatientConsentSerializer,
        responses={201: PatientConsentSerializer}
    )
    @action(detail=True, methods=['post'], url_path='consents')
    def add_consent(self, request, pk=None):
        patient = self.get_object()
        serializer = PatientConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent = serializer.save(patient=patient)

        AuditService.log(
            action='PATIENT_CONSENT_RECORDED',
            request=request,
            resource_type='PatientConsent',
            resource_id=consent.id,
            details={'consent_type': consent.consent_type, 'mrn': patient.medical_record_number}
        )
        return Response(PatientConsentSerializer(consent).data, status=status.HTTP_201_CREATED)
