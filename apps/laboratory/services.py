from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import Role
from apps.audit.services import log_audit_event
from .models import (
    LabTestCatalogue,
    LabTestParameter,
    LabOrder,
    LabOrderItem,
    LabSpecimen,
    LabResult,
    LabResultParameterValue,
)


def create_lab_order(patient_id: int, test_ids: list, user, doctor_id=None, priority='ROUTINE', clinical_indication='', encounter_id=None, admission_id=None) -> LabOrder:
    """
    Creates a new LabOrder with associated LabOrderItem records and generates initial specimen accession records.
    """
    from apps.patients.models import Patient

    if not test_ids:
        raise ValidationError("At least one diagnostic test must be specified.")

    with transaction.atomic():
        patient = Patient.objects.get(id=patient_id)
        
        doctor = None
        if doctor_id:
            from apps.departments.models import Doctor
            doctor = Doctor.objects.filter(id=doctor_id).first()

        lab_order = LabOrder.objects.create(
            patient=patient,
            ordering_doctor=doctor,
            encounter_id=encounter_id,
            admission_id=admission_id,
            clinical_indication=clinical_indication,
            priority=priority,
            status='ORDERED'
        )

        specimen_types_needed = set()

        for test_id in test_ids:
            test = LabTestCatalogue.objects.get(id=test_id)
            LabOrderItem.objects.create(
                order=lab_order,
                lab_test=test,
                status='PENDING'
            )
            if test.specimen_type and test.specimen_type != 'NONE':
                specimen_types_needed.add(test.specimen_type)

        # Create specimen containers for collection
        for spec_type in specimen_types_needed:
            LabSpecimen.objects.create(
                order=lab_order,
                specimen_type=spec_type,
                status='COLLECTED' if priority == 'STAT' else 'COLLECTED'
            )

        log_audit_event(
            action='LAB_ORDER_CREATED',
            entity_type='LabOrder',
            entity_id=lab_order.id,
            user=user,
            details={'order_number': lab_order.order_number, 'patient': patient.full_name, 'tests_count': len(test_ids)}
        )
        return lab_order


def collect_specimen(specimen_id: int, user, notes: str = '') -> LabSpecimen:
    """
    Marks a specimen as collected and updates the associated order items to SAMPLE_COLLECTED.
    """
    with transaction.atomic():
        specimen = LabSpecimen.objects.select_for_update().get(id=specimen_id)
        specimen.status = 'COLLECTED'
        specimen.collected_by = user
        specimen.collected_at = timezone.now()
        specimen.notes = notes
        specimen.save()

        # Update order items
        order = specimen.order
        order.items.filter(status='PENDING').update(status='SAMPLE_COLLECTED')
        if order.status == 'ORDERED':
            order.status = 'COLLECTED'
            order.save()

        log_audit_event(
            action='LAB_SPECIMEN_COLLECTED',
            entity_type='LabSpecimen',
            entity_id=specimen.id,
            user=user,
            details={'accession_number': specimen.accession_number, 'specimen_type': specimen.specimen_type}
        )
        return specimen


def record_test_results(order_item_id: int, parameter_values: list, summary_notes: str, user, correction_reason: str = '') -> LabResult:
    """
    Records laboratory test results with multi-parameter evaluations.
    Enforces that verified/released results cannot be silently overwritten (requires correction_reason & increments version).
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    if user.role not in [Role.LAB_TECHNICIAN, Role.DOCTOR, Role.ADMIN, Role.SUPER_ADMIN] and not user.is_superuser:
        raise PermissionDenied("Only lab technicians or authorized doctors can enter laboratory results.")

    with transaction.atomic():
        order_item = LabOrderItem.objects.select_for_update().get(id=order_item_id)
        existing_result = LabResult.objects.filter(order_item=order_item).first()

        version = 1
        is_corrected = False
        prev_result = None

        if existing_result:
            if existing_result.status in ['VERIFIED', 'RELEASED']:
                if not correction_reason.strip():
                    raise ValidationError("This result has already been verified/released. A correction reason is mandatory to save an amendment.")
                version = existing_result.version + 1
                is_corrected = True
                prev_result = existing_result
            
            # Archive or update
            result = existing_result
            result.version = version
            result.is_corrected = is_corrected
            result.correction_reason = correction_reason
            result.previous_result = prev_result
            result.recorded_by = user
            result.recorded_at = timezone.now()
            result.summary_notes = summary_notes
            result.status = 'PRELIMINARY'
            result.is_released = False
            result.parameter_values.all().delete()
        else:
            result = LabResult(
                order_item=order_item,
                status='PRELIMINARY',
                summary_notes=summary_notes,
                recorded_by=user,
                recorded_at=timezone.now(),
                version=1
            )

        is_critical = False
        overall_abnormal = False

        result.save()

        for p_val in parameter_values:
            param_id = p_val.get('parameter_id') or p_val.get('parameter')
            parameter = LabTestParameter.objects.get(id=param_id)
            val_str = str(p_val.get('value', '')).strip()

            numeric_val = None
            try:
                numeric_val = float(val_str)
            except (ValueError, TypeError):
                numeric_val = None

            flag = 'NORMAL'
            ref_display = parameter.reference_range_text or ""
            if parameter.reference_range_min is not None and parameter.reference_range_max is not None:
                ref_display = f"{parameter.reference_range_min} - {parameter.reference_range_max} {parameter.unit}"

            if numeric_val is not None:
                # Critical check
                if parameter.critical_low is not None and numeric_val < parameter.critical_low:
                    flag = 'CRITICAL_LOW'
                    is_critical = True
                elif parameter.critical_high is not None and numeric_val > parameter.critical_high:
                    flag = 'CRITICAL_HIGH'
                    is_critical = True
                # Range check
                elif parameter.reference_range_min is not None and numeric_val < parameter.reference_range_min:
                    flag = 'LOW'
                    overall_abnormal = True
                elif parameter.reference_range_max is not None and numeric_val > parameter.reference_range_max:
                    flag = 'HIGH'
                    overall_abnormal = True

            LabResultParameterValue.objects.create(
                result=result,
                parameter=parameter,
                value=val_str,
                numeric_value=numeric_val,
                flag=flag,
                reference_range_display=ref_display
            )

        result.is_critical = is_critical
        if is_critical:
            result.overall_interpretation = 'CRITICAL'
            result.critical_alert_sent = True
        elif overall_abnormal:
            result.overall_interpretation = 'ABNORMAL'
        else:
            result.overall_interpretation = 'NORMAL'

        result.save()

        order_item.status = 'PRELIMINARY'
        order_item.save()

        log_audit_event(
            action='LAB_RESULT_RECORDED',
            entity_type='LabResult',
            entity_id=result.id,
            user=user,
            details={
                'test': order_item.lab_test.name,
                'interpretation': result.overall_interpretation,
                'is_critical': result.is_critical,
                'version': result.version
            }
        )
        return result


def verify_and_release_result(result_id: int, user, release_to_patient: bool = True) -> LabResult:
    """
    Verifies and releases laboratory test results to the medical record and patient.
    Enforces authorization: Only doctors, pathologists, or authorized lab staff can verify.
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    if user.role not in [Role.DOCTOR, Role.LAB_TECHNICIAN, Role.ADMIN, Role.SUPER_ADMIN] and not user.is_superuser:
        raise PermissionDenied("Only doctors or senior laboratory personnel can verify and release lab results.")

    with transaction.atomic():
        result = LabResult.objects.select_for_update().get(id=result_id)
        now = timezone.now()

        result.verified_by = user
        result.verified_at = now

        if release_to_patient:
            result.status = 'RELEASED'
            result.is_released = True
            result.released_by = user
            result.released_at = now
            result.order_item.status = 'RELEASED'
        else:
            result.status = 'VERIFIED'
            result.order_item.status = 'VERIFIED'

        result.save()
        result.order_item.save()

        # Check if entire order is complete
        order = result.order_item.order
        all_released = all(item.status in ['RELEASED', 'COMPLETED'] for item in order.items.all())
        if all_released:
            order.status = 'COMPLETED'
            order.save()
        else:
            order.status = 'IN_PROGRESS'
            order.save()

        log_audit_event(
            action='LAB_RESULT_RELEASED' if release_to_patient else 'LAB_RESULT_VERIFIED',
            entity_type='LabResult',
            entity_id=result.id,
            user=user,
            details={
                'test': result.order_item.lab_test.name,
                'status': result.status,
                'order_number': order.order_number
            }
        )
        try:
            from apps.notifications.services import send_notification
            from apps.notifications.models import Notification
            send_notification(
                title=f"Lab Result Released: {result.order_item.lab_test.name}",
                message=f"Diagnostic result released for {order.patient.full_name} (Order {order.order_number}).",
                notification_type=Notification.NotificationType.LAB_RESULT_READY,
                target_role='DOCTOR',
                link='/laboratory',
                severity=Notification.Severity.SUCCESS
            )
        except Exception:
            pass
        return result


def get_critical_lab_alerts():
    """
    Returns all critical / panic laboratory results that require urgent clinical attention.
    """
    return LabResult.objects.filter(
        is_critical=True,
        critical_acknowledged=False
    ).select_related(
        'order_item__order__patient',
        'order_item__lab_test',
        'recorded_by'
    ).order_by('-recorded_at')
