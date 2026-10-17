from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.utils import timezone
from apps.common.permissions import IsStaffMember, IsAdminOrReadOnly, IsPatientOwnerOrStaff
from apps.accounts.models import Role
from .models import Ward, Room, Bed, Admission, InpatientProgressRecord, InpatientCharge
from .serializers import (
    WardSerializer,
    RoomSerializer,
    BedSerializer,
    AdmissionListSerializer,
    AdmissionDetailSerializer,
    AdmissionCreateSerializer,
    BedTransferSerializer,
    DischargeSerializer,
    InpatientProgressRecordSerializer,
    InpatientChargeSerializer,
)
from .services import admit_patient, transfer_bed, discharge_patient


class WardViewSet(viewsets.ModelViewSet):
    queryset = Ward.objects.filter(is_active=True).prefetch_related('rooms__beds')
    serializer_class = WardSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    search_fields = ['name', 'code', 'ward_type']
    filterset_fields = ['ward_type', 'department']

    @action(detail=False, methods=['get'])
    def occupancy_summary(self, request):
        wards = self.get_queryset()
        summary = []
        total_beds = 0
        total_occupied = 0
        total_available = 0

        for w in wards:
            w_total = w.total_beds_count
            w_occ = w.occupied_beds_count
            w_avail = w.available_beds_count
            total_beds += w_total
            total_occupied += w_occ
            total_available += w_avail

            summary.append({
                'ward_id': w.id,
                'name': w.name,
                'code': w.code,
                'ward_type': w.ward_type,
                'total_beds': w_total,
                'occupied_beds': w_occ,
                'available_beds': w_avail,
                'occupancy_rate': w.occupancy_rate,
            })

        overall_occupancy = round((total_occupied / total_beds * 100.0), 1) if total_beds > 0 else 0.0

        return Response({
            'overall_total_beds': total_beds,
            'overall_occupied_beds': total_occupied,
            'overall_available_beds': total_available,
            'overall_occupancy_rate': overall_occupancy,
            'wards': summary
        })


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.filter(is_active=True).select_related('ward').prefetch_related('beds')
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['ward', 'room_type']


class BedViewSet(viewsets.ModelViewSet):
    queryset = Bed.objects.filter(is_active=True).select_related('room__ward')
    serializer_class = BedSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['status', 'bed_type', 'room__ward', 'room']

    @action(detail=False, methods=['get'])
    def available(self, request):
        ward_id = request.query_params.get('ward_id')
        qs = self.get_queryset().filter(status='AVAILABLE')
        if ward_id:
            qs = qs.filter(room__ward_id=ward_id)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class AdmissionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsPatientOwnerOrStaff]
    filterset_fields = ['status', 'admission_type', 'admitting_doctor']
    search_fields = ['admission_number', 'patient__first_name', 'patient__last_name', 'admitting_diagnosis']

    def get_queryset(self):
        user = self.request.user
        qs = Admission.objects.select_related(
            'patient',
            'admitting_doctor',
            'primary_nurse',
            'signed_discharge_by'
        ).prefetch_related(
            'bed_assignments__bed__room__ward',
            'progress_records',
            'charges'
        )

        if not user.is_authenticated:
            return qs.none()

        # Patients can only see their own admissions
        if user.role == Role.PATIENT:
            return qs.filter(patient__user=user)

        # Doctors can see all or prioritize their admissions
        if user.role == Role.DOCTOR:
            assigned_only = self.request.query_params.get('my_patients')
            if assigned_only == 'true' and hasattr(user, 'doctor_profile'):
                return qs.filter(admitting_doctor__user=user)

        # Nurses can view all or filter by assigned
        if user.role == Role.NURSE:
            assigned_only = self.request.query_params.get('my_patients')
            if assigned_only == 'true':
                return qs.filter(
                    models.Q(primary_nurse=user) |
                    models.Q(nurse_assignments__nurse=user, nurse_assignments__is_active=True)
                ).distinct()

        return qs

    def get_serializer_class(self):
        if self.action in ['retrieve']:
            return AdmissionDetailSerializer
        if self.action in ['create']:
            return AdmissionCreateSerializer
        return AdmissionListSerializer

    def create(self, request, *args, **kwargs):
        if not (request.user.is_hospital_staff or request.user.is_superuser):
            raise PermissionDenied("Only hospital clinical staff can admit inpatients.")

        serializer = AdmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        admission = admit_patient(
            patient_id=data['patient_id'],
            admitting_doctor_id=data['admitting_doctor_id'],
            bed_id=data['bed_id'],
            admitting_diagnosis=data['admitting_diagnosis'],
            admission_type=data.get('admission_type', 'ELECTIVE'),
            chief_complaint=data.get('chief_complaint', ''),
            primary_nurse_id=data.get('primary_nurse_id'),
            user=request.user
        )

        detail_serializer = AdmissionDetailSerializer(admission)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='transfer')
    def transfer_bed(self, request, pk=None):
        if not (request.user.is_hospital_staff or request.user.is_superuser):
            raise PermissionDenied("Only hospital clinical staff can transfer inpatient beds.")

        admission = self.get_object()
        serializer = BedTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_assignment = transfer_bed(
            admission_id=admission.id,
            target_bed_id=serializer.validated_data['target_bed_id'],
            transfer_reason=serializer.validated_data['transfer_reason'],
            user=request.user
        )

        detail_serializer = AdmissionDetailSerializer(admission)
        return Response(detail_serializer.data)

    @action(detail=True, methods=['post'])
    def discharge(self, request, pk=None):
        admission = self.get_object()
        
        # Only doctors or admins can authorize and sign discharge
        if request.user.role not in [Role.SUPER_ADMIN, Role.ADMIN, Role.DOCTOR] and not request.user.is_superuser:
            raise PermissionDenied("Only doctors or administrators may authorize and sign an inpatient discharge.")

        serializer = DischargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        discharged_admission = discharge_patient(
            admission_id=admission.id,
            discharge_summary=data['discharge_summary'],
            discharge_instructions=data.get('discharge_instructions', ''),
            discharge_disposition=data.get('discharge_disposition', 'ROUTINE_HOME'),
            follow_up_date=data.get('follow_up_date'),
            user=request.user
        )

        detail_serializer = AdmissionDetailSerializer(discharged_admission)
        return Response(detail_serializer.data)

    @action(detail=True, methods=['post'])
    def add_progress_note(self, request, pk=None):
        admission = self.get_object()
        if request.user.role not in [Role.SUPER_ADMIN, Role.ADMIN, Role.DOCTOR] and not request.user.is_superuser:
            raise PermissionDenied("Only doctors or administrators may author clinical progress records.")

        clinical_findings = request.data.get('clinical_findings')
        if not clinical_findings:
            raise ValidationError({'clinical_findings': 'Clinical findings are required.'})

        assessment = request.data.get('assessment', '')
        orders_and_plan = request.data.get('orders_and_plan', '')
        is_signed = bool(request.data.get('is_signed', False))

        now = timezone.now()
        note = InpatientProgressRecord.objects.create(
            admission=admission,
            author=request.user,
            record_date=now,
            clinical_findings=clinical_findings,
            assessment=assessment,
            orders_and_plan=orders_and_plan,
            is_signed=is_signed,
            signed_at=now if is_signed else None,
            signed_by=request.user if is_signed else None
        )

        serializer = InpatientProgressRecordSerializer(note)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def add_charge(self, request, pk=None):
        admission = self.get_object()
        charge_type = request.data.get('charge_type', 'PROCEDURE')
        description = request.data.get('description')
        unit_price = request.data.get('unit_price')
        quantity = int(request.data.get('quantity', 1))

        if not description or unit_price is None:
            raise ValidationError({'detail': 'Description and unit_price are required.'})

        charge = InpatientCharge.objects.create(
            admission=admission,
            charge_type=charge_type,
            description=description,
            unit_price=unit_price,
            quantity=quantity,
            created_by=request.user
        )

        serializer = InpatientChargeSerializer(charge)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
