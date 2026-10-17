from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Appointment, DoctorSchedule, DoctorLeave, QueueEntry
from .serializers import (
    AppointmentSerializer,
    AppointmentRescheduleSerializer,
    AppointmentCancelSerializer,
    WalkInRegistrationSerializer,
    QueueEntrySerializer,
    DoctorScheduleSerializer,
    DoctorLeaveSerializer
)
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from apps.accounts.models import Role
from apps.common.permissions import IsStaffMember, IsAdminOrReadOnly
from apps.audit.services import AuditService


VALID_APPOINTMENT_TRANSITIONS = {
    'PENDING': ['CONFIRMED', 'CANCELLED'],
    'CONFIRMED': ['CHECKED_IN', 'RESCHEDULED', 'CANCELLED', 'NO_SHOW'],
    'CHECKED_IN': ['IN_CONSULTATION', 'CANCELLED'],
    'IN_CONSULTATION': ['COMPLETED', 'CANCELLED'],
    'RESCHEDULED': ['CONFIRMED', 'CANCELLED'],
    'COMPLETED': [],
    'CANCELLED': [],
    'NO_SHOW': [],
}


@extend_schema_view(
    list=extend_schema(summary="List hospital appointments with status and role filtering"),
    create=extend_schema(summary="Book a new medical appointment with double-booking prevention"),
    retrieve=extend_schema(summary="Retrieve appointment details by ID or reference number")
)
class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'department', 'doctor', 'appointment_date']
    search_fields = ['reference_number', 'first_name', 'last_name', 'phone', 'email']
    ordering_fields = ['created_at', 'appointment_date']

    def get_queryset(self):
        user = self.request.user
        qs = Appointment.objects.all().select_related('department', 'doctor')

        if user and user.is_authenticated:
            if getattr(user, 'is_hospital_staff', False) or user.is_superuser:
                return qs
            return qs.filter(email__iexact=user.email)

        ref = self.request.query_params.get('reference_number')
        if ref:
            return qs.filter(reference_number=ref)
        return qs.none()

    def get_object(self):
        lookup = self.kwargs.get('pk')
        if lookup and str(lookup).startswith('MED-'):
            apt = Appointment.objects.filter(reference_number=lookup).first()
            if apt:
                self.check_object_permissions(self.request, apt)
                return apt
        return super().get_object()

    def perform_create(self, serializer):
        with transaction.atomic():
            appointment = serializer.save(status=serializer.validated_data.get('status', 'PENDING'))
            AuditService.log(
                action='APPOINTMENT_BOOKED',
                request=self.request,
                resource_type='Appointment',
                resource_id=appointment.id,
                details={'ref': appointment.reference_number, 'date': appointment.appointment_date, 'time': appointment.appointment_time}
            )
            try:
                from apps.notifications.services import send_notification
                from apps.notifications.models import Notification
                send_notification(
                    title=f"Appointment Booked: {appointment.patient_full_name}",
                    message=f"Reference {appointment.reference_number} booked for {appointment.appointment_date} at {appointment.appointment_time}.",
                    notification_type=Notification.NotificationType.APPOINTMENT_REMINDER,
                    target_role='RECEPTIONIST',
                    link='/queue',
                    severity=Notification.Severity.INFO
                )
            except Exception:
                pass

    @extend_schema(summary="Discover available appointment slots for a doctor on a specific date")
    @action(detail=False, methods=['get'], url_path='slots')
    def slots(self, request):
        doctor_id = request.query_params.get('doctor_id') or request.query_params.get('doctor')
        date_str = request.query_params.get('date')

        if not doctor_id or not date_str:
            return Response(
                {'error': 'Both doctor_id and date query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            doctor = Doctor.objects.get(pk=doctor_id)
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (Doctor.DoesNotExist, ValueError):
            return Response(
                {'error': 'Invalid doctor_id or date format (expected YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Check if doctor is on approved leave
        is_on_leave = DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__lte=target_date,
            end_date__gte=target_date,
            is_approved=True
        ).exists()

        if is_on_leave:
            return Response({
                'doctor_id': doctor.id,
                'doctor_name': doctor.name,
                'date': date_str,
                'available': False,
                'reason': f'Dr. {doctor.name} is on scheduled leave.',
                'slots': []
            })

        # 2. Get Doctor working schedule for this day of week
        weekday = target_date.weekday()
        schedule = DoctorSchedule.objects.filter(doctor=doctor, day_of_week=weekday, is_active=True).first()

        start_t = schedule.start_time if schedule else time(9, 0)
        end_t = schedule.end_time if schedule else time(17, 0)
        duration = schedule.slot_duration_minutes if schedule else 30

        # Generate time slots
        slots_list = []
        cur_dt = datetime.combine(target_date, start_t)
        end_dt = datetime.combine(target_date, end_t)

        # Existing active bookings on that day
        booked_times = set(
            Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date_str
            ).exclude(
                status__in=['CANCELLED', 'RESCHEDULED', 'NO_SHOW']
            ).values_list('appointment_time', flat=True)
        )

        while cur_dt < end_dt:
            slot_str = cur_dt.strftime('%H:%M')
            is_booked = (slot_str in booked_times) or (cur_dt.strftime('%I:%M %p') in booked_times)
            slots_list.append({
                'time': slot_str,
                'display': cur_dt.strftime('%I:%M %p'),
                'is_booked': is_booked,
                'available': not is_booked
            })
            cur_dt += timedelta(minutes=duration)

        return Response({
            'doctor_id': doctor.id,
            'doctor_name': doctor.name,
            'date': date_str,
            'available': True,
            'slot_count': len(slots_list),
            'slots': slots_list
        })

    @extend_schema(summary="Patient check-in and queue token generation")
    @action(detail=True, methods=['post'], url_path='check-in', permission_classes=[permissions.IsAuthenticated, IsStaffMember])
    def check_in(self, request, pk=None):
        appointment = self.get_object()
        old_status = appointment.status

        # Validate status transition
        if 'CHECKED_IN' not in VALID_APPOINTMENT_TRANSITIONS.get(old_status, []):
            return Response(
                {'error': f"Cannot check-in appointment from status '{old_status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            appointment.status = 'CHECKED_IN'
            appointment.save(update_fields=['status'])

            today = timezone.now().date()
            today_count = QueueEntry.objects.filter(doctor=appointment.doctor, queue_date=today).count()
            token = f"OPD-{today_count + 1:03d}"

            # Try to match existing patient identity
            patient = Patient.objects.filter(phone=appointment.phone).first()

            queue_entry = QueueEntry.objects.create(
                appointment=appointment,
                patient=patient,
                patient_name=appointment.patient_full_name,
                patient_phone=appointment.phone,
                doctor=appointment.doctor,
                department=appointment.department or appointment.doctor.department,
                token_number=token,
                queue_date=today,
                queue_type='SCHEDULED',
                status='WAITING'
            )

            AuditService.log(
                action='PATIENT_CHECKED_IN',
                request=request,
                resource_type='Appointment',
                resource_id=appointment.id,
                details={'ref': appointment.reference_number, 'token': token}
            )

        return Response({
            'message': 'Patient successfully checked in.',
            'appointment': AppointmentSerializer(appointment).data,
            'queue_entry': QueueEntrySerializer(queue_entry).data
        })

    @extend_schema(summary="Reschedule an appointment with double-booking validation", request=AppointmentRescheduleSerializer)
    @action(detail=True, methods=['post'], url_path='reschedule')
    def reschedule(self, request, pk=None):
        appointment = self.get_object()
        serializer = AppointmentRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_date = serializer.validated_data['appointment_date']
        new_time = serializer.validated_data['appointment_time']

        old_status = appointment.status
        if 'RESCHEDULED' not in VALID_APPOINTMENT_TRANSITIONS.get(old_status, []):
            return Response(
                {'error': f"Cannot reschedule appointment from status '{old_status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Check leave
            if appointment.doctor:
                on_leave = DoctorLeave.objects.filter(
                    doctor=appointment.doctor,
                    start_date__lte=new_date,
                    end_date__gte=new_date,
                    is_approved=True
                ).exists()
                if on_leave:
                    return Response(
                        {'error': f"Dr. {appointment.doctor.name} is on leave on {new_date}."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                conflict = Appointment.objects.filter(
                    doctor=appointment.doctor,
                    appointment_date=new_date,
                    appointment_time=new_time
                ).exclude(status__in=['CANCELLED', 'RESCHEDULED', 'NO_SHOW']).exclude(pk=appointment.pk).exists()

                if conflict:
                    return Response(
                        {'error': 'Requested time slot is already booked.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            appointment.appointment_date = new_date
            appointment.appointment_time = new_time
            appointment.status = 'CONFIRMED'
            appointment.save(update_fields=['appointment_date', 'appointment_time', 'status'])

            AuditService.log(
                action='APPOINTMENT_RESCHEDULED',
                request=request,
                resource_type='Appointment',
                resource_id=appointment.id,
                details={'ref': appointment.reference_number, 'new_date': new_date, 'new_time': new_time}
            )
            try:
                from apps.notifications.services import send_notification
                from apps.notifications.models import Notification
                send_notification(
                    title=f"Appointment Rescheduled: {appointment.reference_number}",
                    message=f"Appointment for {appointment.patient_full_name} moved to {new_date} at {new_time}.",
                    notification_type=Notification.NotificationType.APPOINTMENT_CHANGE,
                    target_role='RECEPTIONIST',
                    link='/queue',
                    severity=Notification.Severity.WARNING
                )
            except Exception:
                pass

        return Response(AppointmentSerializer(appointment).data)

    @extend_schema(summary="Cancel an appointment", request=AppointmentCancelSerializer)
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_appointment(self, request, pk=None):
        appointment = self.get_object()
        old_status = appointment.status

        if 'CANCELLED' not in VALID_APPOINTMENT_TRANSITIONS.get(old_status, []):
            return Response(
                {'error': f"Cannot cancel appointment from terminal status '{old_status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            appointment.status = 'CANCELLED'
            appointment.save(update_fields=['status'])

            # Cancel queue entry if waiting
            QueueEntry.objects.filter(appointment=appointment, status='WAITING').update(status='CANCELLED')

            AuditService.log(
                action='APPOINTMENT_CANCELLED',
                request=request,
                resource_type='Appointment',
                resource_id=appointment.id,
                details={'ref': appointment.reference_number, 'previous_status': old_status}
            )
            try:
                from apps.notifications.services import send_notification
                from apps.notifications.models import Notification
                send_notification(
                    title=f"Appointment Cancelled: {appointment.reference_number}",
                    message=f"Appointment for {appointment.patient_full_name} has been cancelled.",
                    notification_type=Notification.NotificationType.APPOINTMENT_CHANGE,
                    target_role='RECEPTIONIST',
                    link='/queue',
                    severity=Notification.Severity.DANGER
                )
            except Exception:
                pass

        return Response(AppointmentSerializer(appointment).data)

    @extend_schema(summary="Register an outpatient walk-in and issue queue token", request=WalkInRegistrationSerializer)
    @action(detail=False, methods=['post'], url_path='walk-in', permission_classes=[permissions.IsAuthenticated, IsStaffMember])
    def walk_in(self, request):
        serializer = WalkInRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            doctor = Doctor.objects.get(pk=data['doctor_id'])
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)

        department = None
        if data.get('department_id'):
            department = Department.objects.filter(pk=data['department_id']).first()
        if not department:
            department = doctor.department

        patient = None
        if data.get('patient_id'):
            patient = Patient.objects.filter(pk=data['patient_id']).first()

        today = timezone.now().date()
        with transaction.atomic():
            today_count = QueueEntry.objects.filter(doctor=doctor, queue_date=today).count()
            token = f"OPD-{today_count + 1:03d}"

            entry = QueueEntry.objects.create(
                patient=patient,
                patient_name=data['patient_name'],
                patient_phone=data.get('patient_phone', ''),
                doctor=doctor,
                department=department,
                token_number=token,
                queue_date=today,
                queue_type='WALK_IN',
                status='WAITING',
                priority=data.get('priority', 1)
            )

            AuditService.log(
                action='WALK_IN_REGISTERED',
                request=request,
                resource_type='QueueEntry',
                resource_id=entry.id,
                details={'token': token, 'doctor': doctor.name, 'priority': entry.priority}
            )

        return Response(QueueEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class QueueEntryViewSet(viewsets.ModelViewSet):
    queryset = QueueEntry.objects.all().select_related('doctor', 'department', 'patient', 'appointment')
    serializer_class = QueueEntrySerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['doctor', 'department', 'queue_date', 'status', 'queue_type']
    search_fields = ['token_number', 'patient_name', 'patient_phone']
    ordering_fields = ['priority', 'check_in_time']

    def get_queryset(self):
        qs = super().get_queryset()
        # Default to today's queue if no explicit queue_date query param
        if 'queue_date' not in self.request.query_params:
            qs = qs.filter(queue_date=timezone.now().date())
        return qs

    @extend_schema(summary="Call patient from waiting area into doctor consultation room")
    @action(detail=True, methods=['post'], url_path='call')
    def call_patient(self, request, pk=None):
        entry = self.get_object()
        entry.status = 'CALLED'
        entry.called_time = timezone.now()
        entry.save(update_fields=['status', 'called_time'])

        AuditService.log(
            action='QUEUE_PATIENT_CALLED',
            request=request,
            resource_type='QueueEntry',
            resource_id=entry.id,
            details={'token': entry.token_number, 'doctor': entry.doctor.name}
        )
        return Response(QueueEntrySerializer(entry).data)


class DoctorScheduleViewSet(viewsets.ModelViewSet):
    queryset = DoctorSchedule.objects.all().select_related('doctor')
    serializer_class = DoctorScheduleSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['doctor', 'day_of_week', 'is_active']


class DoctorLeaveViewSet(viewsets.ModelViewSet):
    queryset = DoctorLeave.objects.all().select_related('doctor')
    serializer_class = DoctorLeaveSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['doctor', 'is_approved']
