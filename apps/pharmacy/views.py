from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, PermissionDenied
from apps.common.permissions import IsStaffMember, IsPharmacist, IsAdmin
from .models import (
    Supplier,
    MedicineCatalogue,
    StockBatch,
    StockMovementLedger,
    PurchaseOrder,
    GoodsReceipt,
    DispenseRecord,
    WastageReturnRecord,
)
from .serializers import (
    SupplierSerializer,
    MedicineCatalogueSerializer,
    StockBatchSerializer,
    StockMovementLedgerSerializer,
    PurchaseOrderSerializer,
    GoodsReceiptSerializer,
    DispenseRecordSerializer,
    WastageReturnRecordSerializer,
)
from .services import (
    receive_goods_shipment,
    dispense_prescription_items,
    record_wastage_or_return,
    get_inventory_alerts,
)


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    search_fields = ['name', 'code', 'contact_person']


class MedicineCatalogueViewSet(viewsets.ModelViewSet):
    queryset = MedicineCatalogue.objects.all().prefetch_related('batches')
    serializer_class = MedicineCatalogueSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    search_fields = ['name', 'generic_name', 'code', 'category']
    filterset_fields = ['category', 'dosage_form', 'is_prescription_required', 'is_active']

    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """Returns low-stock medications and near-expiry / expired batches."""
        alerts = get_inventory_alerts()
        return Response(alerts)


class StockBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockBatch.objects.all().select_related('medication')
    serializer_class = StockBatchSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['medication', 'status']

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Returns currently non-expired batches with positive stock on hand."""
        med_id = request.query_params.get('medication')
        qs = self.queryset.filter(status='ACTIVE', quantity_on_hand__gt=0)
        if med_id:
            qs = qs.filter(medication_id=med_id)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class StockMovementLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovementLedger.objects.all().select_related('medication', 'batch', 'created_by')
    serializer_class = StockMovementLedgerSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    filterset_fields = ['medication', 'movement_type', 'reference_type']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all().select_related('supplier', 'created_by').prefetch_related('items')
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class GoodsReceiptViewSet(viewsets.ModelViewSet):
    queryset = GoodsReceipt.objects.all().select_related('supplier', 'received_by', 'purchase_order').prefetch_related('items')
    serializer_class = GoodsReceiptSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]

    def create(self, request, *args, **kwargs):
        receipt_data = request.data.get('receipt', request.data)
        items_data = request.data.get('items', [])
        if not items_data:
            return Response({'detail': 'Items list is required for goods receipt.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            grn = receive_goods_shipment(receipt_data, items_data, request.user)
            serializer = self.get_serializer(grn)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class DispenseRecordViewSet(viewsets.ModelViewSet):
    queryset = DispenseRecord.objects.all().select_related('patient', 'pharmacist', 'prescription').prefetch_related('items')
    serializer_class = DispenseRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]

    def create(self, request, *args, **kwargs):
        # Strict pharmacist check
        prescription_id = request.data.get('prescription_id')
        items = request.data.get('items', [])
        notes = request.data.get('notes', '')

        if not prescription_id or not items:
            return Response({'detail': 'Prescription ID and items to dispense are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            record = dispense_prescription_items(prescription_id, items, request.user, notes)
            serializer = self.get_serializer(record)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except PermissionDenied as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class WastageReturnViewSet(viewsets.ModelViewSet):
    queryset = WastageReturnRecord.objects.all().select_related('medication', 'batch', 'processed_by')
    serializer_class = WastageReturnRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]

    def create(self, request, *args, **kwargs):
        record_type = request.data.get('record_type')
        medication_id = request.data.get('medication_id')
        batch_id = request.data.get('batch_id')
        quantity = int(request.data.get('quantity', 0))
        reason = request.data.get('reason')
        notes = request.data.get('notes', '')

        try:
            record = record_wastage_or_return(
                record_type=record_type,
                medication_id=medication_id,
                batch_id=batch_id,
                quantity=quantity,
                reason=reason,
                notes=notes,
                user=request.user
            )
            serializer = self.get_serializer(record)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as exc:
            return Response({'detail': str(exc.message if hasattr(exc, 'message') else exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
