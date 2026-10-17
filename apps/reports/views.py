from rest_framework import permissions, status, viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from apps.accounts.models import Role
from .services import (
    get_role_dashboard,
    get_appointments_and_patients_report,
    get_department_activity_report,
    get_admissions_and_occupancy_report,
    get_pharmacy_and_expiry_report,
    get_laboratory_workload_report,
    get_revenue_report,
    get_audit_report,
)


class DashboardOverviewView(APIView):
    """
    Returns role-specific operational metrics and dashboard aggregations.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Retrieve role-tailored operational dashboard overview",
        description="Calculates server-side KPIs for the authenticated user's role."
    )
    def get(self, request):
        target_role = request.query_params.get('role')
        data = get_role_dashboard(request.user, target_role=target_role)
        return Response(data)


class ReportsViewSet(viewsets.ViewSet):
    """
    Operational analytics and reporting endpoints with role-based authorization.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _check_staff(self, request):
        if not (request.user.is_hospital_staff or request.user.is_superuser):
            return Response(
                {"detail": "Access denied. Reports are restricted to authorized healthcare personnel."},
                status=status.HTTP_403_FORBIDDEN
            )
        return None

    def _check_admin(self, request):
        if not (request.user.is_admin or request.user.has_app_permission('reports.view_financial')):
            return Response(
                {"detail": "Access denied. Administrative privileges are required for this report."},
                status=status.HTTP_403_FORBIDDEN
            )
        return None

    def _check_audit_admin(self, request):
        if not (request.user.is_admin or request.user.has_app_permission('audit.view')):
            return Response(
                {"detail": "Access denied. Administrative privileges are required for this report."},
                status=status.HTTP_403_FORBIDDEN
            )
        return None

    @action(detail=False, methods=['get'], url_path='appointments')
    def appointments_report(self, request):
        """Appointment volume, status distribution, and patient registration metrics."""
        err = self._check_staff(request)
        if err: return err

        start = request.query_params.get('start_date')
        end = request.query_params.get('end_date')
        return Response(get_appointments_and_patients_report(start, end))

    @action(detail=False, methods=['get'], url_path='departments')
    def departments_report(self, request):
        """Department operational activity, appointments, doctors, and active queue."""
        err = self._check_staff(request)
        if err: return err

        return Response(get_department_activity_report())

    @action(detail=False, methods=['get'], url_path='admissions')
    def admissions_report(self, request):
        """Inpatient bed occupancy, ward capacity, and admission rates."""
        err = self._check_staff(request)
        if err: return err

        return Response(get_admissions_and_occupancy_report())

    @action(detail=False, methods=['get'], url_path='pharmacy')
    def pharmacy_report(self, request):
        """Pharmacy stock on hand, low-stock alerts, and batch expiry distribution."""
        err = self._check_staff(request)
        if err: return err

        return Response(get_pharmacy_and_expiry_report())

    @action(detail=False, methods=['get'], url_path='laboratory')
    def laboratory_report(self, request):
        """Laboratory test order volume, turnaround metrics, and critical test alerts."""
        err = self._check_staff(request)
        if err: return err

        start = request.query_params.get('start_date')
        end = request.query_params.get('end_date')
        return Response(get_laboratory_workload_report(start, end))

    @action(detail=False, methods=['get'], url_path='revenue')
    def revenue_report(self, request):
        """Financial collections, outstanding balance, discounts, and payment methods."""
        err = self._check_admin(request)
        if err: return err

        start = request.query_params.get('start_date')
        end = request.query_params.get('end_date')
        return Response(get_revenue_report(start, end))

    @action(detail=False, methods=['get'], url_path='audit')
    def audit_report(self, request):
        """Security and access audit log history."""
        err = self._check_audit_admin(request)
        if err: return err

        limit = int(request.query_params.get('limit', 50))
        return Response(get_audit_report(limit))
