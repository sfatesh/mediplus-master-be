from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SupplierViewSet,
    MedicineCatalogueViewSet,
    StockBatchViewSet,
    StockMovementLedgerViewSet,
    PurchaseOrderViewSet,
    GoodsReceiptViewSet,
    DispenseRecordViewSet,
    WastageReturnViewSet,
)

router = DefaultRouter()
router.register(r'pharmacy/suppliers', SupplierViewSet, basename='pharmacy-supplier')
router.register(r'pharmacy/medicines', MedicineCatalogueViewSet, basename='pharmacy-medicine')
router.register(r'pharmacy/batches', StockBatchViewSet, basename='pharmacy-batch')
router.register(r'pharmacy/ledger', StockMovementLedgerViewSet, basename='pharmacy-ledger')
router.register(r'pharmacy/purchase-orders', PurchaseOrderViewSet, basename='pharmacy-po')
router.register(r'pharmacy/goods-receipts', GoodsReceiptViewSet, basename='pharmacy-grn')
router.register(r'pharmacy/dispensations', DispenseRecordViewSet, basename='pharmacy-dispense')
router.register(r'pharmacy/wastage-returns', WastageReturnViewSet, basename='pharmacy-wastage-return')

urlpatterns = [
    path('', include(router.urls)),
]
