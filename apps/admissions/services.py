from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.patients.models import Patient
from apps.departments.models import Doctor
from apps.accounts.models import Role, User
from apps.audit.services import log_audit_event
from .models import Ward, Room, Bed, Admission, BedAssignment, InpatientProgressRecord, InpatientCharge


def admit_patient(
    patient_id: int,
    admitting_doctor_id: int,
    bed_id: int,
    admitting_diagnosis: str,
    admission_type: str = 'ELECTIVE',
    chief_complaint: str = '',
    primary_nurse_id: int = None,
    user=None
) -> Admission:
    """
    Admits a patient to a hospital bed using an atomic transaction.
    Prevents overlapping active assignments for the same bed and ensures
    patients cannot have multiple concurrent active admissions.
    """
    with transaction.atomic():
        try:
            patient = Patient.objects.get(id=patient_id, is_active=True)
        except Patient.DoesNotExist:
            raise ValidationError({'patient_id': 'Active patient not found.'})

        # Check for existing active admission
        existing_active = Admission.objects.filter(patient=patient, status='ADMITTED').exists()
        if existing_active:
            raise ValidationError({'patient_id': f'Patient {patient.full_name} is already admitted.'})

        try:
            doctor = Doctor.objects.get(id=admitting_doctor_id, is_active=True)
        except Doctor.DoesNotExist:
            raise ValidationError({'admitting_doctor_id': 'Active admitting doctor not found.'})

        # Lock bed to prevent race conditions & double-booking
        try:
            bed = Bed.objects.select_for_update().get(id=bed_id, is_active=True)
        except Bed.DoesNotExist:
            raise ValidationError({'bed_id': 'Bed not found.'})

        if bed.status != 'AVAILABLE':
            raise ValidationError({'bed_id': f'Bed {bed.bed_number} is currently {bed.status} and cannot be assigned.'})

        # Double check no active bed assignment exists
        active_assignment = BedAssignment.objects.filter(bed=bed, is_active=True).exists()
        if active_assignment:
            raise ValidationError({'bed_id': f'Bed {bed.bed_number} already has an active assignment.'})

        primary_nurse = None
        if primary_nurse_id:
            try:
                primary_nurse = User.objects.get(id=primary_nurse_id, is_active=True)
            except User.DoesNotExist:
                pass

        # 1. Create Inpatient Admission record
        admission = Admission.objects.create(
            patient=patient,
            admitting_doctor=doctor,
            primary_nurse=primary_nurse,
            admission_date=timezone.now(),
            admission_type=admission_type,
            admitting_diagnosis=admitting_diagnosis,
            chief_complaint=chief_complaint,
            status='ADMITTED'
        )

        # 2. Create active BedAssignment
        BedAssignment.objects.create(
            admission=admission,
            bed=bed,
            assigned_from=timezone.now(),
            is_active=True
        )

        # 3. Update Bed status
        bed.status = 'OCCUPIED'
        bed.save(update_fields=['status', 'updated_at'])

        # 4. Inpatient charge integration: Daily room & bed base charge
        daily_rate = Decimal(bed.room.ward.daily_base_rate) + Decimal(bed.room.daily_rate)
        if daily_rate > Decimal('0.00'):
            InpatientCharge.objects.create(
                admission=admission,
                charge_type='BED_DAY',
                description=f"Day 1 Inpatient Bed Rate ({bed.room.ward.name} - {bed.bed_number})",
                unit_price=daily_rate,
                quantity=1,
                total_amount=daily_rate,
                created_by=user
            )

        log_audit_event(
            action='ADMISSION_CREATED',
            entity_type='Admission',
            entity_id=admission.id,
            user=user,
            details={
                'admission_number': admission.admission_number,
                'patient_id': patient.id,
                'bed_id': bed.id,
                'bed_number': bed.bed_number,
                'ward': bed.room.ward.name
            }
        )

        return admission


def transfer_bed(
    admission_id: int,
    target_bed_id: int,
    transfer_reason: str,
    user=None
) -> BedAssignment:
    """
    Transfers an admitted patient from their current bed to a target bed.
    Executed in an atomic transaction with bed locking to prevent conflicts.
    """
    with transaction.atomic():
        try:
            admission = Admission.objects.select_for_update().get(id=admission_id)
        except Admission.DoesNotExist:
            raise ValidationError({'admission_id': 'Admission not found.'})

        if admission.status != 'ADMITTED':
            raise ValidationError({'admission': f'Cannot transfer bed. Patient admission is {admission.status}.'})

        current_assignment = BedAssignment.objects.select_for_update().filter(
            admission=admission,
            is_active=True
        ).first()

        if not current_assignment:
            raise ValidationError({'admission': 'No active bed assignment found for this admission.'})

        current_bed = current_assignment.bed
        if current_bed.id == target_bed_id:
            raise ValidationError({'target_bed_id': 'Target bed is identical to the current assigned bed.'})

        # Lock target bed
        try:
            target_bed = Bed.objects.select_for_update().get(id=target_bed_id, is_active=True)
        except Bed.DoesNotExist:
            raise ValidationError({'target_bed_id': 'Target bed not found.'})

        if target_bed.status != 'AVAILABLE':
            raise ValidationError({'target_bed_id': f'Target bed {target_bed.bed_number} is {target_bed.status} and cannot receive a patient.'})

        # 1. Close current assignment
        current_assignment.is_active = False
        current_assignment.assigned_to = timezone.now()
        current_assignment.save(update_fields=['is_active', 'assigned_to', 'updated_at'])

        # 2. Release previous bed
        current_bed.status = 'AVAILABLE'
        current_bed.save(update_fields=['status', 'updated_at'])

        # 3. Create new assignment
        new_assignment = BedAssignment.objects.create(
            admission=admission,
            bed=target_bed,
            assigned_from=timezone.now(),
            is_active=True,
            transfer_reason=transfer_reason,
            transferred_by=user
        )

        # 4. Occupy target bed
        target_bed.status = 'OCCUPIED'
        target_bed.save(update_fields=['status', 'updated_at'])

        log_audit_event(
            action='BED_TRANSFERRED',
            entity_type='BedAssignment',
            entity_id=new_assignment.id,
            user=user,
            details={
                'admission_id': admission.id,
                'from_bed': current_bed.bed_number,
                'to_bed': target_bed.bed_number,
                'reason': transfer_reason
            }
        )

        return new_assignment


def discharge_patient(
    admission_id: int,
    discharge_summary: str,
    discharge_instructions: str,
    discharge_disposition: str = 'ROUTINE_HOME',
    follow_up_date=None,
    user=None
) -> Admission:
    """
    Completes patient inpatient stay, releases bed occupancy, and records
    doctor signed discharge summary with follow-up instructions.
    """
    with transaction.atomic():
        try:
            admission = Admission.objects.select_for_update().get(id=admission_id)
        except Admission.DoesNotExist:
            raise ValidationError({'admission_id': 'Admission not found.'})

        if admission.status != 'ADMITTED':
            raise ValidationError({'admission': f'Patient is already {admission.status}. Cannot discharge again.'})

        if not discharge_summary or not discharge_summary.strip():
            raise ValidationError({'discharge_summary': 'Discharge summary is required.'})

        # Release active bed assignment
        active_assignment = BedAssignment.objects.select_for_update().filter(
            admission=admission,
            is_active=True
        ).first()

        if active_assignment:
            active_assignment.is_active = False
            active_assignment.assigned_to = timezone.now()
            active_assignment.save(update_fields=['is_active', 'assigned_to', 'updated_at'])

            bed = active_assignment.bed
            bed.status = 'AVAILABLE'
            bed.save(update_fields=['status', 'updated_at'])

        # Update Admission
        now = timezone.now()
        admission.status = 'DISCHARGED'
        admission.discharge_date = now
        admission.discharge_disposition = discharge_disposition
        admission.discharge_summary = discharge_summary.strip()
        admission.discharge_instructions = discharge_instructions.strip() if discharge_instructions else ''
        admission.follow_up_date = follow_up_date
        admission.is_signed_discharge = True
        admission.signed_discharge_by = user
        admission.signed_discharge_at = now
        admission.save()

        log_audit_event(
            action='PATIENT_DISCHARGED',
            entity_type='Admission',
            entity_id=admission.id,
            user=user,
            details={
                'admission_number': admission.admission_number,
                'discharge_disposition': discharge_disposition,
                'signed_by': user.email if user else None
            }
        )

        return admission
