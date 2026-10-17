from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from apps.common.permissions import IsStaffMember
from apps.accounts.models import Role
from .models import (
    NursePatientAssignment,
    VitalObservation,
    NursingCareNote,
    NursingTask,
    MedicationAdministrationRecord,
    ShiftHandover,
)
from .serializers import (
    NursePatientAssignmentSerializer,
    VitalObservationSerializer,
    NursingCareNoteSerializer,
    NursingTaskSerializer,
    MedicationAdministrationRecordSerializer,
    ShiftHandoverSerializer,
)
from .services import record_vital_observation, administer_medication


class NursePatientAssignmentViewSet(viewsets.ModelViewSet):
    queryset = NursePatientAssignment.objects.select_related(
        'nurse',
        'admission__patient',
        'admission__admitting_doctor'
    ).prefetch_related('admission__bed_assignments__bed__room__ward')
    serializer_class = NursePatientAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['nurse', 'shift', 'assignment_date', 'is_active', 'admission']

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)

    @action(detail=False, methods=['get'])
    def my_patients(self, request):
        user = request.user
        qs = self.get_queryset().filter(nurse=user, is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class VitalObservationViewSet(viewsets.ModelViewSet):
    queryset = VitalObservation.objects.select_related('admission__patient', 'recorded_by')
    serializer_class = VitalObservationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['admission', 'is_critical']
    ordering_fields = ['recorded_at']

    def create(self, request, *args, **kwargs):
        admission_id = request.data.get('admission') or request.data.get('admission_id')
        if not admission_id:
            raise ValidationError({'admission': 'Admission ID is required.'})

        vital = record_vital_observation(
            admission_id=int(admission_id),
            vitals_data=request.data,
            user=request.user
        )
        if vital.is_critical:
            try:
                from apps.notifications.services import send_notification
                from apps.notifications.models import Notification
                send_notification(
                    title=f"CRITICAL VITALS: {vital.admission.patient.full_name}",
                    message=f"Critical vitals recorded in Ward. Alert: {', '.join(vital.critical_alert_reasons or ['Critical Vital Threshold Passed'])}",
                    notification_type=Notification.NotificationType.CRITICAL_ALERT,
                    target_role='NURSE',
                    link='/nursing',
                    severity=Notification.Severity.DANGER
                )
            except Exception:
                pass

        serializer = self.get_serializer(vital)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def critical_alerts(self, request):
        qs = self.get_queryset().filter(is_critical=True).order_by('-recorded_at')[:50]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class NursingCareNoteViewSet(viewsets.ModelViewSet):
    queryset = NursingCareNote.objects.select_related('admission__patient', 'nurse')
    serializer_class = NursingCareNoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['admission', 'shift', 'note_type']

    def perform_create(self, serializer):
        serializer.save(
            nurse=self.request.user,
            is_signed=True,
            signed_at=timezone.now()
        )


class NursingTaskViewSet(viewsets.ModelViewSet):
    queryset = NursingTask.objects.select_related('admission__patient', 'completed_by')
    serializer_class = NursingTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['admission', 'status', 'priority']

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.status = 'COMPLETED'
        task.completed_at = timezone.now()
        task.completed_by = request.user
        task.notes = request.data.get('notes', task.notes)
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)


class MedicationAdministrationRecordViewSet(viewsets.ModelViewSet):
    queryset = MedicationAdministrationRecord.objects.select_related(
        'admission__patient',
        'administered_by',
        'prescription_item'
    )
    serializer_class = MedicationAdministrationRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['admission', 'status']

    @action(detail=True, methods=['post'])
    def administer(self, request, pk=None):
        mar = self.get_object()
        given_status = request.data.get('status', 'GIVEN')
        remarks = request.data.get('remarks')

        updated_mar = administer_medication(
            mar_id=mar.id,
            status=given_status,
            remarks=remarks,
            user=request.user
        )
        serializer = self.get_serializer(updated_mar)
        return Response(serializer.data)


class ShiftHandoverViewSet(viewsets.ModelViewSet):
    queryset = ShiftHandover.objects.select_related(
        'ward',
        'outgoing_nurse',
        'incoming_nurse'
    )
    serializer_class = ShiftHandoverSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['ward', 'shift', 'is_acknowledged']

    def perform_create(self, serializer):
        serializer.save(outgoing_nurse=self.request.user)

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        handover = self.get_object()
        handover.is_acknowledged = True
        handover.incoming_nurse = request.user
        handover.acknowledged_at = timezone.now()
        handover.save()
        serializer = self.get_serializer(handover)
        return Response(serializer.data)
