import importlib
from datetime import datetime, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import RolePermission
from .models import (
    Supplier,
    Product,
    ProductPart,
    Warehouse,
    Stock,
    StockMovement,
    Customer,
    Vehicle,
    LoyaltyLedger,
    ServiceCatalog,
    ServiceOrder,
    ServiceOrderLine,
    ExpenseCategory,
    Expense,
    CreditAccount,
    CreditEntry,
    ExchangeRate,
    Sale,
    SaleItem,
    SalePayment,
    SaleReturn,
    NotificationPreference,
    AuditLog,
    PaymentGatewayTransaction,
    Barcode,
    OfflineSaleBuffer,
)
from .serializers import (
    SupplierSerializer,
    ProductSerializer,
    ProductSplitSerializer,
    ProductPartSerializer,
    WarehouseSerializer,
    StockSerializer,
    StockMovementSerializer,
    CustomerSerializer,
    VehicleSerializer,
    LoyaltyLedgerSerializer,
    ServiceCatalogSerializer,
    ServiceOrderSerializer,
    ServiceOrderWriteSerializer,
    ServiceOrderLineSerializer,
    ExpenseCategorySerializer,
    ExpenseSerializer,
    CreditAccountSerializer,
    CreditEntrySerializer,
    ExchangeRateSerializer,
    SaleSerializer,
    SaleWriteSerializer,
    SaleReturnSerializer,
    SaleReturnReadItemSerializer,
    NotificationPreferenceSerializer,
    AuditLogSerializer,
    PaymentGatewayTransactionSerializer,
    BarcodeSerializer,
    OfflineSaleBufferSerializer,
)
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

User = get_user_model()


class BaseAuthPermission(permissions.IsAuthenticated):
    pass


@extend_schema(tags=["suppliers"])
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by("name")
    serializer_class = SupplierSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]


@extend_schema(tags=["products"])
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("name")
    serializer_class = ProductSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]
    lookup_field = "id"

    @extend_schema(
        request=ProductSplitSerializer,
        responses={201: ProductPartSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Split Example",
                value={
                    "parts": [
                        {"name": "Sub Part A", "quantity": 2, "price_usd": "5.00"},
                        {"name": "Sub Part B", "quantity": 1, "price_usd": "10.00"},
                    ]
                },
            )
        ],
        description="Split a product into individually sellable parts. Auto-fills price_uzs if omitted.",
    )
    @action(detail=True, methods=["post"], url_path="split")
    def split(self, request, id=None):
        product = self.get_object()
        serializer = ProductSplitSerializer(
            data=request.data, context={"product": product}
        )
        serializer.is_valid(raise_exception=True)
        parts = serializer.save()
        return Response(
            ProductPartSerializer(parts, many=True).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["warehouses"])
class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all().order_by("name")
    serializer_class = WarehouseSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]


@extend_schema(tags=["stocks"])
class StockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Stock.objects.select_related("warehouse", "product", "part").all()
    serializer_class = StockSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE, User.Roles.ACCOUNTANT]


@extend_schema(tags=["stock-movements"])
class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related(
        "warehouse_from", "warehouse_to", "product", "part"
    ).all()
    serializer_class = StockMovementSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]
    http_method_names = ["get", "post", "head", "options"]


@extend_schema(tags=["customers"])
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().order_by("first_name", "last_name")
    serializer_class = CustomerSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.CASHIER, User.Roles.ACCOUNTANT]


@extend_schema(tags=["vehicles"])
class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related("customer").all()
    serializer_class = VehicleSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.CASHIER, User.Roles.ACCOUNTANT]


@extend_schema(tags=["loyalty"])
class LoyaltyLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LoyaltyLedger.objects.select_related("customer").all()
    serializer_class = LoyaltyLedgerSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.CASHIER, User.Roles.ACCOUNTANT]


@extend_schema(tags=["services"])
class ServiceCatalogViewSet(viewsets.ModelViewSet):
    queryset = ServiceCatalog.objects.all().order_by("name")
    serializer_class = ServiceCatalogSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.CASHIER]


@extend_schema(tags=["service-orders"])
class ServiceOrderViewSet(viewsets.ModelViewSet):
    queryset = ServiceOrder.objects.select_related(
        "customer", "vehicle"
    ).prefetch_related("lines")
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.CASHIER, User.Roles.WAREHOUSE]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ServiceOrderWriteSerializer
        return ServiceOrderSerializer

    @extend_schema(responses=ServiceOrderSerializer)
    def create(self, request, *args, **kwargs):  # noqa: D401
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            ServiceOrderSerializer(order).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["expenses"])
class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all().order_by("name")
    serializer_class = ExpenseCategorySerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.ACCOUNTANT]


@extend_schema(tags=["expenses"])
class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related("category", "recorded_by").all()
    serializer_class = ExpenseSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.ACCOUNTANT]


@extend_schema(tags=["credit"])
class CreditAccountViewSet(viewsets.ModelViewSet):
    queryset = CreditAccount.objects.select_related(
        "customer", "supplier"
    ).prefetch_related("entries")
    serializer_class = CreditAccountSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.ACCOUNTANT]


@extend_schema(tags=["credit"])
class CreditEntryViewSet(viewsets.ModelViewSet):
    queryset = CreditEntry.objects.select_related("account").all()
    serializer_class = CreditEntrySerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.ACCOUNTANT]


@extend_schema(tags=["exchange-rates"])
class ExchangeRateViewSet(viewsets.ModelViewSet):
    queryset = ExchangeRate.objects.all().order_by("-effective_date")
    serializer_class = ExchangeRateSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.ACCOUNTANT]


@extend_schema(tags=["sales"])
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.select_related("warehouse", "customer").prefetch_related(
        "items", "payments"
    )
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.CASHIER]

    def get_serializer_class(self):
        if self.action == "create":
            return SaleWriteSerializer
        return SaleSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="finalize")
    def finalize(self, request, pk=None):
        sale = self.get_object()
        sale.finalize(actor=request.user)
        return Response(SaleSerializer(sale).data)

    @action(detail=True, methods=["post"], url_path="add-payment")
    def add_payment(self, request, pk=None):
        sale = self.get_object()
        serializer = SalePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        SalePayment.objects.create(sale=sale, **serializer.validated_data)
        return Response(SaleSerializer(sale).data)


@extend_schema(tags=["sales"])
class SaleReturnViewSet(viewsets.ModelViewSet):
    queryset = SaleReturn.objects.select_related("sale").prefetch_related("items")
    serializer_class = SaleReturnSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.CASHIER]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        for entry in response.data:
            return_id = entry["id"]
            entry["items"] = SaleReturnReadItemSerializer(
                SaleReturn.objects.get(pk=return_id).items.all(), many=True
            ).data
        return response


@extend_schema(tags=["notifications"])
class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    queryset = NotificationPreference.objects.select_related("customer").all()
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.CASHIER]


@extend_schema(tags=["audit"])
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.ACCOUNTANT]


@extend_schema(tags=["payments"])
class PaymentGatewayTransactionViewSet(viewsets.ModelViewSet):
    queryset = PaymentGatewayTransaction.objects.select_related("sale").all()
    serializer_class = PaymentGatewayTransactionSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.ACCOUNTANT]


@extend_schema(tags=["barcodes"])
class BarcodeViewSet(viewsets.ModelViewSet):
    queryset = Barcode.objects.select_related("product").all()
    serializer_class = BarcodeSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]


@extend_schema(tags=["offline"])
class OfflineSaleBufferViewSet(viewsets.ModelViewSet):
    queryset = OfflineSaleBuffer.objects.all()
    serializer_class = OfflineSaleBufferSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        serializer.save()


@extend_schema(tags=["reports"])
class ReportingViewSet(viewsets.ViewSet):
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.ACCOUNTANT]

    def list(self, request):
        today = datetime.utcnow().date()
        daily_total = (
            Sale.objects.filter(created_at__date=today)
            .aggregate(total=Sum("total_uzs"))
            .get("total")
            or 0
        )
        monthly_total = (
            Sale.objects.filter(
                created_at__year=today.year, created_at__month=today.month
            )
            .aggregate(total=Sum("total_uzs"))
            .get("total")
            or 0
        )
        yearly_total = (
            Sale.objects.filter(created_at__year=today.year)
            .aggregate(total=Sum("total_uzs"))
            .get("total")
            or 0
        )
        inventory_count = Stock.objects.aggregate(total=Sum("quantity"))
        dead_stock = Stock.objects.filter(
            updated_at__lt=timezone.now() - timedelta(days=90)
        ).count()
        return Response(
            {
                "sales": {
                    "daily": daily_total,
                    "monthly": monthly_total,
                    "yearly": yearly_total,
                },
                "inventory": {
                    "total_items": inventory_count.get("total") or 0,
                    "dead_stock_count": dead_stock,
                },
                "credit_outstanding": CreditAccount.objects.aggregate(
                    total=Sum("balance_uzs")
                )["total"]
                or 0,
                "service_orders": ServiceOrder.objects.values("status").annotate(
                    count=Count("id")
                ),
            }
        )

    @action(detail=False, methods=["get"], url_path="export/excel")
    def export_excel(self, request):
        rows = Sale.objects.values_list("sale_number", "total_uzs", "created_at")
        lines = ["sale_number,total_uzs,created_at"]
        for sale_number, total, created_at in rows:
            lines.append(f"{sale_number},{total},{created_at:%Y-%m-%d %H:%M:%S}")
        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=report.csv"
        return response

    @action(detail=False, methods=["get"], url_path="export/pdf")
    def export_pdf(self, request):
        try:
            canvas_module = importlib.import_module("reportlab.pdfgen.canvas")
            pagesizes_module = importlib.import_module("reportlab.lib.pagesizes")
        except ModuleNotFoundError:  # pragma: no cover - optional dependency
            return Response(
                {"detail": "PDF export requires reportlab. Install to enable."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        buffer = BytesIO()
        pdf = canvas_module.Canvas(buffer, pagesize=pagesizes_module.letter)
        pdf.drawString(100, 750, "Sales Report")
        for idx, sale in enumerate(Sale.objects.order_by("-created_at")[:25], start=1):
            pdf.drawString(
                100, 750 - idx * 20, f"{sale.sale_number} - {sale.total_uzs} UZS"
            )
        pdf.save()
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=report.pdf"
        return response
