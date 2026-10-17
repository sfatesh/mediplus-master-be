from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Q, Avg
from apps.accounts.models import Role, User
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment, QueueEntry
from apps.clinical.models import Encounter, ClinicalNote, Prescription
from apps.admissions.models import Ward, Room, Bed, Admission
from apps.nursing.models import NursePatientAssignment, VitalObservation, NursingTask
from apps.pharmacy.models import MedicineCatalogue, StockBatch, DispenseRecord
from apps.laboratory.models import LabOrder, LabOrderItem, LabResult
from apps.billing.models import Invoice, Payment, Refund
from apps.audit.models import AuditLog


# -----------------------------------------------------------------------------
# OPERATIONAL REPORTS
# -----------------------------------------------------------------------------

def get_appointments_and_patients_report(start_date=None, end_date=None):
    """
    Aggregates appointment statistics and patient registrations in the specified period.
    """
    today = timezone.now().date()
    start = start_date or (today - timedelta(days=30)).isoformat()
    end = end_date or today.isoformat()

    # Filter appointments by appointment_date string (format YYYY-MM-DD)
    apt_qs = Appointment.objects.filter(appointment_date__gte=str(start), appointment_date__lte=str(end))

    total_appointments = apt_qs.count()
    status_counts = apt_qs.values('status').annotate(count=Count('id')).order_by('-count')

    dept_counts = apt_qs.values('department__name').annotate(count=Count('id')).order_by('-count')
    doctor_counts = apt_qs.values('doctor__name').annotate(count=Count('id')).order_by('-count')

    # Patient registrations
    patient_qs = Patient.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    total_patients_registered = patient_qs.count()
    gender_breakdown = patient_qs.values('gender').annotate(count=Count('id'))
    blood_group_breakdown = patient_qs.values('blood_group').annotate(count=Count('id'))

    return {
        "period": {"start_date": str(start), "end_date": str(end)},
        "total_appointments": total_appointments,
        "status_breakdown": list(status_counts),
        "department_breakdown": [
            {"department": d['department__name'] or 'Unassigned', "count": d['count']} for d in dept_counts
        ],
        "doctor_breakdown": [
            {"doctor": doc['doctor__name'] or 'Unassigned', "count": doc['count']} for doc in doctor_counts
        ],
        "patients_registered": total_patients_registered,
        "gender_breakdown": list(gender_breakdown),
        "blood_group_breakdown": list(blood_group_breakdown),
    }


def get_department_activity_report():
    """
    Returns department operational metrics: doctors, appointments, consultations, and active queues.
    """
    departments = Department.objects.filter(is_active=True)
    results = []

    for dept in departments:
        docs_count = Doctor.objects.filter(department=dept, is_active=True).count()
        apts_count = Appointment.objects.filter(department=dept).count()
        consultations_count = Encounter.objects.filter(doctor__department=dept, status='COMPLETED').count()
        active_queue_count = QueueEntry.objects.filter(
            department=dept,
            status__in=['WAITING', 'CALLED', 'IN_CONSULTATION']
        ).count()

        results.append({
            "id": dept.id,
            "name": dept.name,
            "icon": dept.icon,
            "doctors_count": docs_count,
            "appointments_count": apts_count,
            "consultations_count": consultations_count,
            "active_queue_count": active_queue_count,
        })

    return {"departments": results}


def get_admissions_and_occupancy_report():
    """
    Calculates overall and ward-specific bed occupancy, admissions, and discharges.
    """
    total_beds = Bed.objects.count()
    occupied_beds = Bed.objects.filter(status='OCCUPIED').count()
    vacant_beds = Bed.objects.filter(status='AVAILABLE').count()
    occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0

    wards = Ward.objects.filter(is_active=True)
    ward_stats = []
    for ward in wards:
        w_total = Bed.objects.filter(room__ward=ward).count()
        w_occ = Bed.objects.filter(room__ward=ward, status='OCCUPIED').count()
        w_vac = Bed.objects.filter(room__ward=ward, status='AVAILABLE').count()
        w_rate = round((w_occ / w_total * 100), 1) if w_total > 0 else 0.0

        ward_stats.append({
            "id": ward.id,
            "name": ward.name,
            "code": ward.code,
            "total_beds": w_total,
            "occupied_beds": w_occ,
            "vacant_beds": w_vac,
            "occupancy_rate": w_rate
        })

    active_admissions = Admission.objects.filter(status='ADMITTED').count()
    discharges_total = Admission.objects.filter(status='DISCHARGED').count()

    return {
        "overall": {
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "vacant_beds": vacant_beds,
            "occupancy_rate_percentage": occupancy_rate,
            "active_admissions": active_admissions,
            "total_discharges": discharges_total,
        },
        "wards": ward_stats
    }


def get_pharmacy_and_expiry_report():
    """
    Aggregates pharmacy catalog, stock levels, low-stock items, and batch expiry distribution.
    """
    today = timezone.now().date()
    in_30_days = today + timedelta(days=30)
    in_90_days = today + timedelta(days=90)

    total_medicines = MedicineCatalogue.objects.filter(is_active=True).count()
    active_batches = StockBatch.objects.filter(is_active=True)
    total_batches_count = active_batches.count()

    total_stock_units = active_batches.aggregate(total=Sum('quantity_on_hand'))['total'] or 0

    expired_batches = active_batches.filter(expiry_date__lt=today).count()
    expiring_30_days = active_batches.filter(expiry_date__gte=today, expiry_date__lte=in_30_days).count()
    expiring_90_days = active_batches.filter(expiry_date__gt=in_30_days, expiry_date__lte=in_90_days).count()

    # Low stock: quantity_on_hand <= 20
    low_stock_batches = active_batches.filter(quantity_on_hand__lte=20, quantity_on_hand__gt=0).count()
    out_of_stock_batches = active_batches.filter(quantity_on_hand=0).count()

    low_stock_items = []
    for b in active_batches.filter(quantity_on_hand__lte=20).select_related('medication')[:10]:
        low_stock_items.append({
            "medication_name": b.medication.name,
            "batch_number": b.batch_number,
            "current_quantity": b.quantity_on_hand,
            "expiry_date": str(b.expiry_date),
            "status": "OUT_OF_STOCK" if b.quantity_on_hand == 0 else "LOW_STOCK"
        })

    dispensations_count = DispenseRecord.objects.count()

    return {
        "total_medicines": total_medicines,
        "total_batches": total_batches_count,
        "total_stock_units": total_stock_units,
        "expired_batches_count": expired_batches,
        "expiring_within_30_days": expiring_30_days,
        "expiring_within_90_days": expiring_90_days,
        "low_stock_count": low_stock_batches,
        "out_of_stock_count": out_of_stock_batches,
        "low_stock_items": low_stock_items,
        "total_dispensations": dispensations_count,
    }


def get_laboratory_workload_report(start_date=None, end_date=None):
    """
    Aggregates laboratory diagnostics workload, status progress, and turnaround statistics.
    """
    today = timezone.now().date()
    start = start_date or (today - timedelta(days=30)).isoformat()
    end = end_date or today.isoformat()

    orders_qs = LabOrder.objects.filter(ordered_at__date__gte=start, ordered_at__date__lte=end)
    total_orders = orders_qs.count()

    status_breakdown = orders_qs.values('status').annotate(count=Count('id'))

    items_qs = LabOrderItem.objects.filter(order__in=orders_qs)
    category_breakdown = items_qs.values('lab_test__category').annotate(count=Count('id'))
    critical_count = LabResult.objects.filter(is_critical=True, created_at__date__gte=start, created_at__date__lte=end).count()

    return {
        "period": {"start_date": str(start), "end_date": str(end)},
        "total_orders": total_orders,
        "status_breakdown": list(status_breakdown),
        "category_breakdown": [
            {"category": c['lab_test__category'] or 'GENERAL', "count": c['count']} for c in category_breakdown
        ],
        "critical_results_count": critical_count,
    }


def get_revenue_report(start_date=None, end_date=None):
    """
    Returns revenue, payments, discounts, refunds, and collections breakdown.
    """
    from apps.billing.services import get_financial_summary_report
    return get_financial_summary_report(start_date, end_date)


def get_audit_report(limit=50):
    """
    Returns audit trail actions count and latest security access events.
    """
    total_events = AuditLog.objects.count()
    action_counts = AuditLog.objects.values('action').annotate(count=Count('id')).order_by('-count')

    recent_logs = []
    for log in AuditLog.objects.select_related('user').order_by('-created_at')[:limit]:
        recent_logs.append({
            "id": log.id,
            "timestamp": log.created_at.isoformat(),
            "user_name": log.user.full_name if log.user else 'System / Anonymous',
            "user_email": log.user.email if log.user else 'system@mediplus.com',
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "ip_address": log.ip_address or '127.0.0.1',
        })

    return {
        "total_audit_events": total_events,
        "action_breakdown": list(action_counts),
        "recent_logs": recent_logs,
    }


# -----------------------------------------------------------------------------
# ROLE-SPECIFIC DASHBOARD AGGREGATION
# -----------------------------------------------------------------------------

def get_role_dashboard(user, target_role=None):
    """
    Aggregates operational dashboard data tailored for the user's role.
    If user is ADMIN, they may preview another role's dashboard using target_role.
    """
    role = user.role
    if user.role == Role.ADMIN and target_role:
        role = target_role

    today = timezone.now().date()
    today_str = str(today)

    if role == Role.ADMIN:
        return _get_admin_dashboard(today, today_str)
    elif role == Role.DOCTOR:
        return _get_doctor_dashboard(user, today, today_str)
    elif role == Role.RECEPTIONIST:
        return _get_receptionist_dashboard(today, today_str)
    elif role == Role.NURSE:
        return _get_nurse_dashboard(user, today)
    elif role == Role.PHARMACIST:
        return _get_pharmacist_dashboard(today)
    elif role == Role.LAB_TECHNICIAN:
        return _get_lab_technician_dashboard(today)
    elif role == Role.PATIENT:
        return _get_patient_dashboard(user, today, today_str)
    else:
        return _get_admin_dashboard(today, today_str)


def _get_admin_dashboard(today, today_str):
    total_patients = Patient.objects.filter(is_active=True).count()
    total_doctors = Doctor.objects.filter(is_active=True).count()
    today_apts = Appointment.objects.filter(appointment_date=today_str).count()

    total_beds = Bed.objects.count()
    occupied_beds = Bed.objects.filter(status='OCCUPIED').count()
    occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0

    invoiced_sum = Invoice.objects.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    collected_sum = Invoice.objects.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')
    outstanding_sum = Invoice.objects.aggregate(s=Sum('balance_due'))['s'] or Decimal('0.00')

    low_stock = StockBatch.objects.filter(quantity_on_hand__lte=20, is_active=True).count()
    pending_labs = LabOrder.objects.filter(status__in=['ORDERED', 'SAMPLE_COLLECTED', 'PROCESSING']).count()

    # Appointment breakdown for today
    today_stats = Appointment.objects.filter(appointment_date=today_str).values('status').annotate(count=Count('id'))

    # Recent Audit Log Activity
    recent_audits = []
    for al in AuditLog.objects.select_related('user').order_by('-created_at')[:6]:
        recent_audits.append({
            "user_name": al.user.full_name if al.user else 'System',
            "action": al.action,
            "resource_type": al.resource_type,
            "timestamp": al.created_at.strftime('%H:%M:%S'),
        })

    return {
        "role": "ADMIN",
        "kpis": {
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "today_appointments": today_apts,
            "occupied_beds": occupied_beds,
            "total_beds": total_beds,
            "occupancy_rate": occupancy_rate,
            "total_revenue": float(collected_sum),
            "outstanding_balance": float(outstanding_sum),
            "low_stock_count": low_stock,
            "pending_lab_tests": pending_labs,
        },
        "appointment_stats": list(today_stats),
        "recent_activity": recent_audits,
    }


def _get_doctor_dashboard(user, today, today_str):
    # Match doctor by email or name
    doctor = Doctor.objects.filter(email=user.email).first() or Doctor.objects.filter(is_active=True).first()

    apts_qs = Appointment.objects.filter(doctor=doctor, appointment_date=today_str) if doctor else Appointment.objects.none()
    today_apts_count = apts_qs.count()
    completed_apts = apts_qs.filter(status='COMPLETED').count()

    # Appointments list for today
    appointments_list = []
    for a in apts_qs.order_by('appointment_time')[:10]:
        appointments_list.append({
            "id": a.id,
            "reference_number": a.reference_number,
            "patient_name": a.patient_full_name,
            "appointment_time": a.appointment_time,
            "status": a.status,
            "department": a.department.name if a.department else '',
        })

    # Admitted patients under doctor
    assigned_inpatients = []
    if doctor:
        admissions = Admission.objects.filter(admitting_doctor=doctor, status='ADMITTED').select_related('patient')[:6]
        for adm in admissions:
            bed_str = 'Unassigned'
            bed_assign = adm.current_bed_assignment
            if bed_assign and bed_assign.bed and bed_assign.bed.room:
                bed_str = f"{bed_assign.bed.room.ward.code}-{bed_assign.bed.bed_number}"
            assigned_inpatients.append({
                "id": adm.id,
                "patient_name": adm.patient.full_name,
                "mrn": adm.patient.medical_record_number,
                "admission_date": str(adm.admission_date),
                "bed": bed_str,
                "diagnosis": adm.admitting_diagnosis,
            })

    # Pending Clinical Notes & Unreleased Lab Orders
    unsigned_notes = ClinicalNote.objects.filter(encounter__doctor=doctor, is_signed=False).count() if doctor else 0
    pending_labs = LabOrder.objects.filter(ordering_doctor=doctor, status__in=['ORDERED', 'SAMPLE_COLLECTED', 'PROCESSING']).count() if doctor else 0

    return {
        "role": "DOCTOR",
        "doctor_profile": {
            "name": doctor.name if doctor else user.full_name,
            "position": doctor.position if doctor else "Attending Physician",
            "department": doctor.department.name if doctor and doctor.department else "General Practice",
        },
        "kpis": {
            "today_appointments_count": today_apts_count,
            "completed_appointments": completed_apts,
            "active_inpatients_count": len(assigned_inpatients),
            "unsigned_notes_count": unsigned_notes,
            "pending_lab_orders": pending_labs,
        },
        "today_appointments": appointments_list,
        "assigned_inpatients": assigned_inpatients,
    }


def _get_receptionist_dashboard(today, today_str):
    all_today = Appointment.objects.filter(appointment_date=today_str)
    total_today = all_today.count()
    checked_in = all_today.filter(status='CHECKED_IN').count()
    completed = all_today.filter(status='COMPLETED').count()

    # Active Waiting Queue Entries
    active_queue = []
    for q in QueueEntry.objects.filter(queue_date=today, status__in=['WAITING', 'CALLED']).select_related('doctor', 'department').order_by('token_number')[:15]:
        active_queue.append({
            "id": q.id,
            "token_number": q.token_number,
            "patient_name": q.patient_name,
            "doctor_name": q.doctor.name if q.doctor else 'Unassigned',
            "department_name": q.department.name if q.department else '',
            "status": q.status,
            "queue_time": q.created_at.strftime('%H:%M'),
        })

    return {
        "role": "RECEPTIONIST",
        "kpis": {
            "total_today_appointments": total_today,
            "checked_in_count": checked_in,
            "completed_count": completed,
            "waiting_queue_count": len(active_queue),
        },
        "active_queue": active_queue,
    }


def _get_nurse_dashboard(user, today):
    # Nurse patient assignments
    assignments = NursePatientAssignment.objects.filter(nurse=user, is_active=True).select_related('admission', 'admission__patient')
    assigned_patients = []
    for a in assignments:
        adm = a.admission
        bed_str = 'N/A'
        bed_assign = adm.current_bed_assignment
        if bed_assign and bed_assign.bed:
            bed_str = bed_assign.bed.bed_number
        assigned_patients.append({
            "assignment_id": a.id,
            "admission_id": adm.id,
            "patient_name": adm.patient.full_name,
            "mrn": adm.patient.medical_record_number,
            "bed": bed_str,
            "shift": a.shift,
        })

    # If no specific assignments, show general active admissions
    if not assigned_patients:
        for adm in Admission.objects.filter(status='ADMITTED').select_related('patient')[:8]:
            bed_str = 'N/A'
            bed_assign = adm.current_bed_assignment
            if bed_assign and bed_assign.bed:
                bed_str = bed_assign.bed.bed_number
            assigned_patients.append({
                "assignment_id": adm.id,
                "admission_id": adm.id,
                "patient_name": adm.patient.full_name,
                "mrn": adm.patient.medical_record_number,
                "bed": bed_str,
                "shift": "GENERAL",
            })

    # Critical observations recorded in last 24h
    cutoff = timezone.now() - timedelta(hours=24)
    critical_vitals = []
    for v in VitalObservation.objects.filter(is_critical=True, recorded_at__gte=cutoff).select_related('admission__patient').order_by('-recorded_at')[:8]:
        critical_vitals.append({
            "patient_name": v.admission.patient.full_name,
            "recorded_at": v.recorded_at.strftime('%H:%M'),
            "temperature_c": v.temperature_c,
            "heart_rate": v.pulse_rate,
            "bp": f"{v.blood_pressure_systolic}/{v.blood_pressure_diastolic}" if v.blood_pressure_systolic else 'N/A',
            "spo2": v.spo2_percent,
            "alert_reasons": v.critical_alert_reasons or ["Critical Vitals Triggered"],
        })

    # Pending care tasks
    pending_tasks = []
    for t in NursingTask.objects.filter(status__in=['PENDING', 'IN_PROGRESS']).select_related('admission__patient').order_by('due_time')[:8]:
        pending_tasks.append({
            "id": t.id,
            "patient_name": t.admission.patient.full_name,
            "title": t.title,
            "priority": t.priority,
            "due_time": t.due_time.strftime('%H:%M') if t.due_time else 'Today',
            "status": t.status,
        })

    return {
        "role": "NURSE",
        "kpis": {
            "assigned_patients_count": len(assigned_patients),
            "critical_observations_count": len(critical_vitals),
            "pending_care_tasks_count": len(pending_tasks),
        },
        "assigned_patients": assigned_patients,
        "critical_observations": critical_vitals,
        "pending_care_tasks": pending_tasks,
    }


def _get_pharmacist_dashboard(today):
    # Prescriptions waiting for dispensing
    pending_prescriptions = []
    for rx in Prescription.objects.filter(status='AUTHORIZED').select_related('patient', 'prescriber', 'encounter__doctor').order_by('-created_at')[:10]:
        doc_name = rx.prescriber.full_name if rx.prescriber else (rx.encounter.doctor.name if rx.encounter and rx.encounter.doctor else 'Hospital Doctor')
        pending_prescriptions.append({
            "id": rx.id,
            "prescription_number": rx.prescription_number,
            "patient_name": rx.patient.full_name,
            "doctor_name": doc_name,
            "date": rx.created_at.strftime('%Y-%m-%d %H:%M'),
            "items_count": rx.items.count(),
        })

    dispensed_today = DispenseRecord.objects.filter(dispense_date=today).count()

    # Low stock & Expiry
    in_30_days = today + timedelta(days=30)
    low_stock_batches = StockBatch.objects.filter(quantity_on_hand__lte=20, is_active=True).count()
    expired_batches = StockBatch.objects.filter(expiry_date__lt=today, is_active=True).count()
    expiring_soon = StockBatch.objects.filter(expiry_date__gte=today, expiry_date__lte=in_30_days, is_active=True).count()

    return {
        "role": "PHARMACIST",
        "kpis": {
            "pending_dispensing_count": len(pending_prescriptions),
            "dispensed_today_count": dispensed_today,
            "low_stock_batches": low_stock_batches,
            "expired_batches": expired_batches,
            "expiring_soon_count": expiring_soon,
        },
        "pending_prescriptions": pending_prescriptions,
    }


def _get_lab_technician_dashboard(today):
    pending_orders = []
    for o in LabOrder.objects.filter(status__in=['ORDERED', 'SAMPLE_COLLECTED', 'PROCESSING']).select_related('patient', 'ordering_doctor').order_by('-ordered_at')[:10]:
        pending_orders.append({
            "id": o.id,
            "order_number": o.order_number,
            "patient_name": o.patient.full_name,
            "ordering_doctor": o.ordering_doctor.name if o.ordering_doctor else 'Hospital Doctor',
            "priority": o.priority,
            "status": o.status,
            "ordered_at": o.ordered_at.strftime('%Y-%m-%d %H:%M'),
        })

    samples_to_collect = LabOrder.objects.filter(status='ORDERED').count()
    processing_count = LabOrder.objects.filter(status='PROCESSING').count()
    released_today = LabOrder.objects.filter(status='RELEASED', updated_at__date=today).count()
    critical_results = LabResult.objects.filter(is_critical=True).count()

    return {
        "role": "LAB_TECHNICIAN",
        "kpis": {
            "total_pending_orders": len(pending_orders),
            "samples_to_collect": samples_to_collect,
            "processing_count": processing_count,
            "released_today": released_today,
            "critical_results_count": critical_results,
        },
        "pending_orders": pending_orders,
    }


def _get_patient_dashboard(user, today, today_str):
    # Match patient by email or user
    patient = Patient.objects.filter(email=user.email).first() or Patient.objects.filter(is_active=True).first()

    upcoming_apts = []
    if patient:
        apts = Appointment.objects.filter(phone=patient.phone).order_by('-appointment_date')[:5]
        for a in apts:
            upcoming_apts.append({
                "id": a.id,
                "reference_number": a.reference_number,
                "doctor_name": a.doctor.name if a.doctor else 'Hospital Specialist',
                "department": a.department.name if a.department else 'General',
                "appointment_date": a.appointment_date,
                "appointment_time": a.appointment_time,
                "status": a.status,
            })

    # Released Lab Results
    released_labs = []
    if patient:
        orders = LabOrder.objects.filter(patient=patient, status='RELEASED').order_by('-updated_at')[:5]
        for o in orders:
            released_labs.append({
                "id": o.id,
                "order_number": o.order_number,
                "order_date": str(o.order_date),
                "items_count": o.items.count(),
                "status": o.status,
            })

    # Prescriptions
    active_prescriptions = []
    if patient:
        for rx in Prescription.objects.filter(patient=patient).order_by('-created_at')[:5]:
            active_prescriptions.append({
                "id": rx.id,
                "prescription_number": rx.prescription_number,
                "doctor_name": rx.doctor.name if rx.doctor else 'Hospital Doctor',
                "date": rx.created_at.strftime('%Y-%m-%d'),
                "status": rx.status,
            })

    # Invoices & Balance Due
    invoices_list = []
    total_billed = Decimal('0.00')
    total_paid = Decimal('0.00')
    total_due = Decimal('0.00')

    if patient:
        for inv in Invoice.objects.filter(patient=patient).order_by('-issue_date')[:5]:
            total_billed += inv.total_amount
            total_paid += inv.amount_paid
            total_due += inv.balance_due
            invoices_list.append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "issue_date": str(inv.issue_date),
                "total_amount": float(inv.total_amount),
                "amount_paid": float(inv.amount_paid),
                "balance_due": float(inv.balance_due),
                "status": inv.status,
            })

    return {
        "role": "PATIENT",
        "patient_profile": {
            "name": patient.full_name if patient else user.full_name,
            "mrn": patient.medical_record_number if patient else "MRN-PENDING",
            "blood_group": patient.blood_group if patient else "O+",
            "gender": patient.gender if patient else "OTHER",
        },
        "kpis": {
            "upcoming_appointments_count": len(upcoming_apts),
            "released_labs_count": len(released_labs),
            "prescriptions_count": len(active_prescriptions),
            "total_billed": float(total_billed),
            "total_paid": float(total_paid),
            "total_due": float(total_due),
        },
        "upcoming_appointments": upcoming_apts,
        "released_labs": released_labs,
        "active_prescriptions": active_prescriptions,
        "invoices": invoices_list,
    }
