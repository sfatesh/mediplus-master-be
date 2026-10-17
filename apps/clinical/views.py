from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Encounter, ClinicalNote, Prescription, PrescriptionItem
from .serializers import (
    EncounterSerializer,
    StartEncounterSerializer,
    ClinicalNoteSerializer,
    AmendNoteSerializer,
    PrescriptionSerializer,
    PrescriptionItemSerializer
)
from apps.accounts.models import Role
from apps.patients.models import Patient
from apps.departments.models import Doctor
from apps.appointments.models import Appointment, QueueEntry
from apps.common.permissions import IsStaffMember, IsDoctor
from apps.audit.services import AuditService


@extend_schema_view(
    list=extend_schema(summary="List patient encounters"),
    retrieve=extend_schema(summary="Retrieve encounter details by ID")
)
class EncounterViewSet(viewsets.ModelViewSet):
    serializer_class = EncounterSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'encounter_type', 'patient', 'doctor']
    search_fields = ['encounter_number', 'patient__first_name', 'patient__last_name', 'patient__medical_record_number', 'chief_complaint']
    ordering_fields = ['started_at', 'status']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Encounter.objects.none()

        # Patients are restricted strictly to their own clinical encounters
        if user.role == Role.PATIENT:
            return Encounter.objects.filter(patient__user=user).select_related('patient', 'doctor', 'queue_entry')

        # Doctors see encounters for their doctor profile (or all if admin/staff)
        if user.role == Role.DOCTOR:
            # If linked to a doctor profile, show their patients, or staff view
            return Encounter.objects.all().select_related('patient', 'doctor', 'queue_entry')

        # Other hospital staff / Admins see all encounters
        if user.is_hospital_staff or user.is_superuser:
            return Encounter.objects.all().select_related('patient', 'doctor', 'queue_entry')

        return Encounter.objects.none()

    @extend_schema(summary="Start a new clinical patient encounter", request=StartEncounterSerializer)
    @action(detail=False, methods=['post'], url_path='start', permission_classes=[permissions.IsAuthenticated, IsStaffMember])
    def start_encounter(self, request):
        serializer = StartEncounterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            patient = Patient.objects.get(pk=data['patient_id'])
            doctor = Doctor.objects.get(pk=data['doctor_id'])
        except (Patient.DoesNotExist, Doctor.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        appointment = None
        if data.get('appointment_id'):
            appointment = Appointment.objects.filter(pk=data['appointment_id']).first()

        queue_entry = None
        if data.get('queue_entry_id'):
            queue_entry = QueueEntry.objects.filter(pk=data['queue_entry_id']).first()

        with transaction.atomic():
            encounter = Encounter.objects.create(
                patient=patient,
                doctor=doctor,
                attending_user=request.user,
                appointment=appointment,
                queue_entry=queue_entry,
                encounter_type=data.get('encounter_type', 'OUTPATIENT'),
                status='IN_PROGRESS',
                chief_complaint=data.get('chief_complaint', ''),
                vitals=data.get('vitals', {})
            )

            # Update queue status
            if queue_entry:
                queue_entry.status = 'IN_CONSULTATION'
                queue_entry.save(update_fields=['status'])

            # Update appointment status
            if appointment:
                appointment.status = 'IN_CONSULTATION'
                appointment.save(update_fields=['status'])

            AuditService.log(
                action='CLINICAL_ENCOUNTER_STARTED',
                request=request,
                resource_type='Encounter',
                resource_id=encounter.id,
                details={'encounter_number': encounter.encounter_number, 'patient_id': patient.id, 'doctor_id': doctor.id}
            )

        return Response(EncounterSerializer(encounter).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Complete consultation encounter")
    @action(detail=True, methods=['post'], url_path='complete', permission_classes=[permissions.IsAuthenticated, IsStaffMember])
    def complete_encounter(self, request, pk=None):
        encounter = self.get_object()
        if encounter.status == 'COMPLETED':
            return Response({'message': 'Encounter is already completed.'}, status=status.HTTP_200_OK)

        with transaction.atomic():
            encounter.status = 'COMPLETED'
            encounter.completed_at = timezone.now()
            encounter.save(update_fields=['status', 'completed_at'])

            if encounter.queue_entry:
                encounter.queue_entry.status = 'COMPLETED'
                encounter.queue_entry.completed_time = timezone.now()
                encounter.queue_entry.save(update_fields=['status', 'completed_time'])

            if encounter.appointment:
                encounter.appointment.status = 'COMPLETED'
                encounter.appointment.save(update_fields=['status'])

            AuditService.log(
                action='CLINICAL_ENCOUNTER_COMPLETED',
                request=request,
                resource_type='Encounter',
                resource_id=encounter.id,
                details={'encounter_number': encounter.encounter_number}
            )

        return Response(EncounterSerializer(encounter).data)

    @extend_schema(summary="Add clinical note to encounter", request=ClinicalNoteSerializer)
    @action(detail=True, methods=['post'], url_path='notes', permission_classes=[permissions.IsAuthenticated, IsStaffMember])
    def add_note(self, request, pk=None):
        encounter = self.get_object()
        serializer = ClinicalNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(encounter=encounter, author=request.user)

        AuditService.log(
            action='CLINICAL_NOTE_CREATED',
            request=request,
            resource_type='ClinicalNote',
            resource_id=note.id,
            details={'encounter_number': encounter.encounter_number, 'version': note.version}
        )
        return Response(ClinicalNoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Add prescription to encounter", request=PrescriptionSerializer)
    @action(detail=True, methods=['post'], url_path='prescriptions', permission_classes=[permissions.IsAuthenticated, IsStaffMember])
    def add_prescription(self, request, pk=None):
        encounter = self.get_object()
        serializer = PrescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prescription = serializer.save(
            encounter=encounter,
            patient=encounter.patient,
            prescriber=request.user
        )

        AuditService.log(
            action='PRESCRIPTION_CREATED',
            request=request,
            resource_type='Prescription',
            resource_id=prescription.id,
            details={'prescription_number': prescription.prescription_number}
        )
        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)


class ClinicalNoteViewSet(viewsets.ModelViewSet):
    queryset = ClinicalNote.objects.all().select_related('encounter', 'author', 'signed_by')
    serializer_class = ClinicalNoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_signed:
            return Response(
                {'error': 'Signed clinical notes are immutable and cannot be modified. Use the amendment workflow to record an auditable revision.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Sign and lock a clinical note")
    @action(detail=True, methods=['post'], url_path='sign', permission_classes=[permissions.IsAuthenticated, IsDoctor])
    def sign(self, request, pk=None):
        note = self.get_object()
        if note.is_signed:
            return Response({'error': 'Clinical note is already signed and locked.'}, status=status.HTTP_400_BAD_REQUEST)

        note.is_signed = True
        note.signed_at = timezone.now()
        note.signed_by = request.user
        note.save(update_fields=['is_signed', 'signed_at', 'signed_by'])

        AuditService.log(
            action='CLINICAL_NOTE_SIGNED',
            request=request,
            resource_type='ClinicalNote',
            resource_id=note.id,
            details={'signed_by': request.user.email, 'version': note.version}
        )
        return Response(ClinicalNoteSerializer(note).data)

    @extend_schema(summary="Create an auditable amendment to a signed note", request=AmendNoteSerializer)
    @action(detail=True, methods=['post'], url_path='amend', permission_classes=[permissions.IsAuthenticated, IsDoctor])
    def amend(self, request, pk=None):
        original_note = self.get_object()
        serializer = AmendNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            new_note = ClinicalNote.objects.create(
                encounter=original_note.encounter,
                author=request.user,
                subjective=data['subjective'],
                objective=data['objective'],
                assessment=data['assessment'],
                plan=data['plan'],
                diagnoses=data.get('diagnoses', original_note.diagnoses),
                follow_up_instructions=data.get('follow_up_instructions', original_note.follow_up_instructions),
                follow_up_date=data.get('follow_up_date', original_note.follow_up_date),
                version=original_note.version + 1,
                amendment_reason=data['amendment_reason'],
                previous_version=original_note,
                is_signed=False
            )

            AuditService.log(
                action='CLINICAL_NOTE_AMENDED',
                request=request,
                resource_type='ClinicalNote',
                resource_id=new_note.id,
                details={'previous_note_id': original_note.id, 'new_version': new_note.version, 'reason': data['amendment_reason']}
            )

        return Response(ClinicalNoteSerializer(new_note).data, status=status.HTTP_201_CREATED)


class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.all().prefetch_related('items').select_related('patient', 'prescriber', 'encounter')
    serializer_class = PrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Prescription.objects.none()

        if user.role == Role.PATIENT:
            return Prescription.objects.filter(patient__user=user).prefetch_related('items')

        if user.is_hospital_staff or user.is_superuser:
            return Prescription.objects.all().prefetch_related('items')

        return Prescription.objects.none()

    @extend_schema(summary="Authorize and electronically sign a prescription")
    @action(detail=True, methods=['post'], url_path='authorize', permission_classes=[permissions.IsAuthenticated, IsDoctor])
    def authorize(self, request, pk=None):
        prescription = self.get_object()
        if prescription.status == 'AUTHORIZED':
            return Response({'error': 'Prescription is already authorized.'}, status=status.HTTP_400_BAD_REQUEST)

        prescription.status = 'AUTHORIZED'
        prescription.authorized_at = timezone.now()
        prescription.prescriber = request.user
        prescription.save(update_fields=['status', 'authorized_at', 'prescriber'])

        AuditService.log(
            action='PRESCRIPTION_AUTHORIZED',
            request=request,
            resource_type='Prescription',
            resource_id=prescription.id,
            details={'prescription_number': prescription.prescription_number, 'prescriber': request.user.email}
        )
        return Response(PrescriptionSerializer(prescription).data)
