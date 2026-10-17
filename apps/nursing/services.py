from typing import Tuple, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.audit.services import log_audit_event
from .models import (
    Admission,
    Ward,
    NursePatientAssignment,
    VitalObservation,
    NursingCareNote,
    NursingTask,
    MedicationAdministrationRecord,
    ShiftHandover,
)


def evaluate_vital_alerts(vitals: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Evaluates clinical vitals against standard hospital physiological alert criteria.
    Flags critical decompensation, severe hypoxia, hypertensive crisis, or shock.
    """
    alerts = []

    def _to_int(val):
        if val in (None, ''):
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def _to_float(val):
        if val in (None, ''):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    # Blood Pressure checks
    sbp = _to_int(vitals.get('blood_pressure_systolic'))
    dbp = _to_int(vitals.get('blood_pressure_diastolic'))
    if sbp is not None:
        if sbp >= 180:
            alerts.append(f"Hypertensive Crisis: Systolic BP {sbp} mmHg (>= 180)")
        elif sbp < 90:
            alerts.append(f"Hypotension Alert: Systolic BP {sbp} mmHg (< 90)")

    if dbp is not None:
        if dbp >= 110:
            alerts.append(f"Critical Diastolic BP: {dbp} mmHg (>= 110)")
        elif dbp < 50:
            alerts.append(f"Low Diastolic BP: {dbp} mmHg (< 50)")

    # Oxygenation
    spo2 = _to_int(vitals.get('spo2_percent'))
    if spo2 is not None and spo2 < 92:
        alerts.append(f"Hypoxia Alert: SpO2 {spo2}% (< 92%) - Oxygen therapy evaluation required")

    # Heart Rate / Pulse
    pulse = _to_int(vitals.get('pulse_rate'))
    if pulse is not None:
        if pulse > 120:
            alerts.append(f"Severe Tachycardia: Heart rate {pulse} bpm (> 120)")
        elif pulse < 50:
            alerts.append(f"Bradycardia Alert: Heart rate {pulse} bpm (< 50)")

    # Temperature
    temp_val = _to_float(vitals.get('temperature_c'))
    if temp_val is not None:
        if temp_val >= 38.5:
            alerts.append(f"High Grade Pyrexia: Temperature {temp_val} °C (>= 38.5 °C)")
        elif temp_val < 35.5:
            alerts.append(f"Hypothermia Alert: Temperature {temp_val} °C (< 35.5 °C)")

    # Respiratory Rate
    rr = _to_int(vitals.get('respiratory_rate'))
    if rr is not None:
        if rr > 24:
            alerts.append(f"Tachypnea: Respiratory rate {rr} breaths/min (> 24)")
        elif rr < 10:
            alerts.append(f"Bradypnea / Hypoventilation: Respiratory rate {rr} breaths/min (< 10)")

    # Neurological / GCS
    gcs = _to_int(vitals.get('gcs_score'))
    if gcs is not None and gcs <= 8:
        alerts.append(f"Severe Coma / Altered Mental Status: GCS {gcs} (<= 8)")

    # Severe Pain
    pain = _to_int(vitals.get('pain_score'))
    if pain is not None and pain >= 8:
        alerts.append(f"Severe Pain Crisis: Score {pain}/10 (>= 8)")

    return (len(alerts) > 0, alerts)


def record_vital_observation(admission_id: int, vitals_data: Dict[str, Any], user) -> VitalObservation:
    """
    Records bedside vital signs, checks alert thresholds, and logs critical events.
    """
    try:
        admission = Admission.objects.get(id=admission_id, status='ADMITTED')
    except Admission.DoesNotExist:
        raise ValidationError({'admission_id': 'Admitted patient admission not found.'})

    is_critical, alert_reasons = evaluate_vital_alerts(vitals_data)

    vital = VitalObservation.objects.create(
        admission=admission,
        recorded_by=user,
        recorded_at=timezone.now(),
        temperature_c=vitals_data.get('temperature_c'),
        pulse_rate=vitals_data.get('pulse_rate'),
        blood_pressure_systolic=vitals_data.get('blood_pressure_systolic'),
        blood_pressure_diastolic=vitals_data.get('blood_pressure_diastolic'),
        respiratory_rate=vitals_data.get('respiratory_rate'),
        spo2_percent=vitals_data.get('spo2_percent'),
        pain_score=vitals_data.get('pain_score'),
        gcs_score=vitals_data.get('gcs_score'),
        fluid_intake_ml=vitals_data.get('fluid_intake_ml'),
        fluid_output_ml=vitals_data.get('fluid_output_ml'),
        is_critical=is_critical,
        critical_alert_reasons=alert_reasons,
        action_taken=vitals_data.get('action_taken')
    )

    if is_critical:
        log_audit_event(
            action='CRITICAL_VITAL_ALERT',
            entity_type='VitalObservation',
            entity_id=vital.id,
            user=user,
            details={
                'admission_id': admission.id,
                'patient_name': admission.patient.full_name,
                'alerts': alert_reasons
            }
        )

    return vital


def administer_medication(
    mar_id: int,
    status: str,
    remarks: str = None,
    user=None
) -> MedicationAdministrationRecord:
    """
    Updates the Medication Administration Record (MAR) when a nurse gives, holds,
    or documents a missed medication dose.
    """
    try:
        mar = MedicationAdministrationRecord.objects.get(id=mar_id)
    except MedicationAdministrationRecord.DoesNotExist:
        raise ValidationError({'mar_id': 'Medication administration record not found.'})

    mar.status = status
    mar.administered_time = timezone.now() if status == 'GIVEN' else None
    mar.administered_by = user
    if remarks:
        mar.remarks = remarks
    mar.save()

    log_audit_event(
        action='MEDICATION_ADMINISTERED',
        entity_type='MedicationAdministrationRecord',
        entity_id=mar.id,
        user=user,
        details={
            'medication': mar.medication_name,
            'dose': mar.dose,
            'status': status,
            'patient_id': mar.admission.patient_id
        }
    )

    return mar
