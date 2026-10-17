from decimal import Decimal
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import Role
from apps.common.permissions import IsStaffMember, IsAdmin, IsPatientOwnerOrStaff
from .models import (
    ServiceCatalogue,
    Invoice,
    Payment,
    Refund,
    InsurancePolicy,
    InsuranceClaim,
    InvoiceAdjustment,
)
from .serializers import (
    ServiceCatalogueSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    RefundSerializer,
    InsurancePolicySerializer,
    InsuranceClaimSerializer,
    InvoiceAdjustmentSerializer,
)
from .services import (
    create_invoice,
    record_payment,
    request_refund,
    approve_and_process_refund,
    adjust_invoice,
    get_financial_summary_report,
)


class ServiceCatalogueViewSet(viewsets.ModelViewSet):
    queryset = ServiceCatalogue.objects.all()
    serializer_class = ServiceCatalogueSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    search_fields = ['name', 'code', 'category']
    filterset_fields = ['category', 'is_active']


class InsurancePolicyViewSet(viewsets.ModelViewSet):
    queryset = InsurancePolicy.objects.all().select_related('patient')
    serializer_class = InsurancePolicySerializer
    permission_classes = [permissions.IsAuthenticated, IsPatientOwnerOrStaff]
    filterset_fields = ['patient', 'is_active']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return InsurancePolicy.objects.none()
        if user.role == Role.PATIENT:
            return self.queryset.filter(patient__user=user)
        return self.queryset


class InsuranceClaimViewSet(viewsets.ModelViewSet):
    queryset = InsuranceClaim.objects.all().select_related('invoice', 'policy__patient')
    serializer_class = InsuranceClaimSerializer
    permission_classes = [permissions.IsAuthenticated, IsPatientOwnerOrStaff]
    filterset_fields = ['invoice', 'status']


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().select_related('patient', 'created_by').prefetch_related(
        'items',
        'payments',
        'refunds',
        'adjustments'
    )
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsPatientOwnerOrStaff]
    filterset_fields = ['patient', 'status']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Invoice.objects.none()
        if user.role == Role.PATIENT:
            return self.queryset.filter(patient__user=user)
        return self.queryset

    def create(self, request, *args, **kwargs):
        if not (request.user.is_admin or request.user.has_app_permission('billing.invoice_create')):
            raise PermissionDenied("You do not have permission to generate invoices.")

        patient_id = request.data.get('patient_id')
        items = request.data.get('items', [])
        due_date = request.data.get('due_date')
        discount_amount = Decimal(str(request.data.get('discount_amount', 0)))
        discount_reason = request.data.get('discount_reason', '')
        encounter_id = request.data.get('encounter_id')
        admission_id = request.data.get('admission_id')
        notes = request.data.get('notes', '')

        try:
            invoice = create_invoice(
                patient_id=patient_id,
                items_data=items,
                user=request.user,
                due_date=due_date,
                discount_amount=discount_amount,
                discount_reason=discount_reason,
                encounter_id=encounter_id,
                admission_id=admission_id,
                notes=notes
            )
            serializer = self.get_serializer(invoice)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except PermissionDenied as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='record-payment')
    def record_invoice_payment(self, request, pk=None):
        if not (request.user.is_admin or request.user.has_app_permission('billing.payment_record')):
            raise PermissionDenied("You do not have permission to record payments.")

        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method', 'CASH')
        transaction_reference = request.data.get('transaction_reference', '')
        notes = request.data.get('notes', '')

        if not amount or not transaction_reference:
            return Response({'detail': 'Amount and transaction_reference are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = record_payment(
                invoice_id=pk,
                amount=Decimal(str(amount)),
                payment_method=payment_method,
                transaction_reference=transaction_reference,
                user=request.user,
                notes=notes
            )
            serializer = PaymentSerializer(payment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except PermissionDenied as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='adjust')
    def adjust(self, request, pk=None):
        if not (request.user.is_admin or request.user.has_app_permission('billing.refund_approve')):
            raise PermissionDenied("You do not have permission to adjust invoices.")

        adj_type = request.data.get('adjustment_type', 'DISCOUNT_AMENDMENT')
        new_discount = request.data.get('new_discount', 0)
        reason = request.data.get('reason', '')

        try:
            adj = adjust_invoice(
                invoice_id=pk,
                adjustment_type=adj_type,
                new_discount=Decimal(str(new_discount)),
                reason=reason,
                user=request.user
            )
            serializer = InvoiceAdjustmentSerializer(adj)
            return Response(serializer.data)
        except PermissionDenied as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='financial-report', permission_classes=[permissions.IsAuthenticated])
    def financial_report(self, request):
        if not (request.user.is_admin or request.user.has_app_permission('billing.financial_reports')):
            return Response({'detail': 'You do not have permission to view financial reports.'}, status=status.HTTP_403_FORBIDDEN)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        report = get_financial_summary_report(start_date=start_date, end_date=end_date)
        return Response(report)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.all().select_related('invoice__patient', 'received_by')
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsPatientOwnerOrStaff]
    filterset_fields = ['invoice', 'status', 'payment_method']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Payment.objects.none()
        if user.role == Role.PATIENT:
            return self.queryset.filter(patient__user=user)
        return self.queryset

    @action(detail=True, methods=['post'], url_path='request-refund')
    def request_refund_action(self, request, pk=None):
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')

        try:
            refund = request_refund(
                payment_id=pk,
                amount=Decimal(str(amount)),
                reason=reason,
                user=request.user
            )
            serializer = RefundSerializer(refund)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class RefundViewSet(viewsets.ModelViewSet):
    queryset = Refund.objects.all().select_related('payment', 'invoice__patient', 'requested_by', 'approved_by')
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['invoice', 'status']

    @action(detail=True, methods=['post'], url_path='approve-process', permission_classes=[permissions.IsAuthenticated, IsAdmin])
    def approve_process(self, request, pk=None):
        try:
            refund = approve_and_process_refund(pk, request.user)
            serializer = self.get_serializer(refund)
            return Response(serializer.data)
        except PermissionDenied as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
