import importlib
from datetime import datetime, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum, Count, Q, F, Prefetch
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import RolePermission
from .models import (
    Supplier,
    Category,
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
    OrderList,
    InventoryCheck,
    InventoryCheckLine,
)
from .serializers import (
    SupplierSerializer,
    CategorySerializer,
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
    SalePaymentSerializer,
    SaleReturnSerializer,
    SaleReturnReadItemSerializer,
    NotificationPreferenceSerializer,
    AuditLogSerializer,
    PaymentGatewayTransactionSerializer,
    BarcodeSerializer,
    OfflineSaleBufferSerializer,
    OrderListSerializer,
    InventoryCheckSerializer,
    InventoryCheckWriteSerializer,
    InventoryCheckLineSerializer,
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


@extend_schema(tags=["categories"])
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]

    @extend_schema(
        responses={200: CategorySerializer(many=True)},
        description="Get all root categories (categories without parents)",
    )
    @action(detail=False, methods=["get"], url_path="root")
    def root_categories(self, request):
        """Return only root-level categories"""
        root_cats = Category.objects.filter(parent__isnull=True).order_by("name")
        serializer = self.get_serializer(root_cats, many=True)
        return Response(serializer.data)


@extend_schema(tags=["products"])
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("name")
    serializer_class = ProductSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]
    lookup_field = "id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code", "oem_number", "barcodes__code"]
    ordering_fields = ["name", "code", "created_at", "price_uzs"]

    @extend_schema(
        description="Search products by name, code, OEM number, or barcode",
        responses={200: ProductSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search_products(self, request):
        """Advanced product search by multiple criteria"""
        query = request.query_params.get("q", "")
        category = request.query_params.get("category", None)
        supplier = request.query_params.get("supplier", None)

        queryset = self.get_queryset()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(code__icontains=query)
                | Q(oem_number__icontains=query)
                | Q(barcodes__code__icontains=query)
            ).distinct()

        if category:
            queryset = queryset.filter(category_id=category)

        if supplier:
            queryset = queryset.filter(supplier_id=supplier)

        serializer = self.get_serializer(queryset[:50], many=True)
        return Response(serializer.data)

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
class StockViewSet(viewsets.ModelViewSet):
    queryset = Stock.objects.select_related("warehouse", "product", "part").all()
    serializer_class = StockSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE, User.Roles.ACCOUNTANT]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    @extend_schema(
        description="Get all low stock items (below threshold)",
        responses={200: StockSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        """Return items with stock below threshold"""
        low_stock_items = [stock for stock in self.get_queryset() if stock.is_low_stock]
        serializer = self.get_serializer(low_stock_items, many=True)
        return Response(serializer.data)

    @extend_schema(
        description="Get all out of stock items",
        responses={200: StockSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="out-of-stock")
    def out_of_stock(self, request):
        """Return items that are completely out of stock"""
        out_of_stock_items = self.get_queryset().filter(quantity=0)
        serializer = self.get_serializer(out_of_stock_items, many=True)
        return Response(serializer.data)

    @extend_schema(
        description="Generate low stock report for printing",
        responses={200: {"type": "string", "format": "binary"}},
    )
    @action(detail=False, methods=["get"], url_path="low-stock-report")
    def low_stock_report(self, request):
        """Generate CSV report of low stock items"""
        low_stock_items = [stock for stock in self.get_queryset() if stock.is_low_stock]

        lines = [
            "Warehouse,Product Code,Product Name,Current Stock,Threshold,Reorder Qty"
        ]
        for stock in low_stock_items:
            product_code = (
                stock.product.code if stock.product else f"PART-{stock.part_id}"
            )
            product_name = stock.product.name if stock.product else stock.part.name
            lines.append(
                f"{stock.warehouse.name},{product_code},{product_name},"
                f"{stock.quantity},{stock.low_stock_threshold},{stock.reorder_quantity}"
            )

        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="low_stock_report.csv"'
        return response

    @extend_schema(
        description="Get dead stock (items not moved in 90+ days)",
        responses={200: StockSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="dead-stock")
    def dead_stock(self, request):
        """Return items with no movement in the last 90 days"""
        ninety_days_ago = timezone.now() - timedelta(days=90)
        dead_stock_items = self.get_queryset().filter(updated_at__lt=ninety_days_ago)
        serializer = self.get_serializer(dead_stock_items, many=True)
        return Response(serializer.data)


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

    @extend_schema(
        description="Get detailed purchase history for a customer",
        responses={200: SaleSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="purchase-history")
    def purchase_history(self, request, pk=None):
        """Return all sales for this customer with items"""
        customer = self.get_object()
        sales = (
            Sale.objects.filter(customer=customer)
            .prefetch_related("items__product", "items__part", "payments")
            .order_by("-created_at")
        )

        # Pagination
        page = self.paginate_queryset(sales)
        if page is not None:
            serializer = SaleSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = SaleSerializer(sales, many=True)
        return Response(serializer.data)

    @extend_schema(
        description="Get customer statistics (total spent, number of purchases, etc.)",
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["get"], url_path="statistics")
    def statistics(self, request, pk=None):
        """Return purchase statistics for this customer"""
        customer = self.get_object()
        sales = Sale.objects.filter(customer=customer, status=Sale.Status.PAID)

        stats = {
            "total_purchases": sales.count(),
            "total_spent_uzs": sales.aggregate(total=Sum("total_uzs"))["total"] or 0,
            "total_spent_usd": sales.aggregate(total=Sum("total_usd"))["total"] or 0,
            "average_purchase_uzs": sales.aggregate(avg=Sum("total_uzs"))["avg"] or 0,
            "loyalty_points": customer.loyalty_points,
            "first_purchase": (
                sales.order_by("created_at").first().created_at
                if sales.exists()
                else None
            ),
            "last_purchase": (
                sales.order_by("-created_at").first().created_at
                if sales.exists()
                else None
            ),
        }

        return Response(stats)


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

    @extend_schema(
        description="Print service receipt",
        responses={200: {"type": "string", "content": {"text/plain": {}}}},
    )
    @action(detail=True, methods=["get"], url_path="print-receipt")
    def print_receipt(self, request, pk=None):
        """Generate service order receipt"""
        order = self.get_object()

        lines = []
        lines.append("=" * 40)
        lines.append("SERVICE RECEIPT")
        lines.append(f"Order #: {order.number}")
        lines.append(f"Date: {order.opened_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 40)

        if order.customer:
            lines.append(f"Customer: {order.customer.full_name}")
            lines.append(f"Phone: {order.customer.phone}")

        if order.vehicle:
            lines.append(f"Vehicle: {order.vehicle.plate_number}")
            if order.vehicle.make:
                lines.append(f"Make/Model: {order.vehicle.make} {order.vehicle.model}")

        lines.append("-" * 40)
        lines.append("SERVICES:")

        for line in order.lines.all():
            service_name = line.service.name if line.service else line.description
            if line.is_free:
                lines.append(f"{service_name} (FREE)")
            else:
                lines.append(f"{service_name}")
                lines.append(
                    f"  {line.quantity} x {line.price_uzs:,.2f} = {line.quantity * line.price_uzs:,.2f} UZS"
                )

        lines.append("-" * 40)

        if order.is_complimentary:
            lines.append("*** COMPLIMENTARY SERVICE ***")
            lines.append("TOTAL: 0.00 UZS")
        else:
            lines.append(f"TOTAL: {order.total_uzs:,.2f} UZS")

        lines.append("=" * 40)
        lines.append("Thank you for choosing our service!")
        lines.append("=" * 40)

        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="service_receipt_{order.number}.txt"'
        )
        return response


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

    @extend_schema(
        description="Print receipt in thermal format (57/80mm)",
        responses={200: {"type": "string", "content": {"text/plain": {}}}},
    )
    @action(detail=True, methods=["get"], url_path="print-receipt/thermal")
    def print_thermal_receipt(self, request, pk=None):
        """Generate thermal receipt text (for 57mm/80mm printers)"""
        sale = self.get_object()

        lines = []
        lines.append("=" * 40)
        lines.append("RECEIPT")
        lines.append(f"Sale #: {sale.sale_number}")
        lines.append(f"Date: {sale.created_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 40)

        if sale.customer:
            lines.append(f"Customer: {sale.customer.full_name}")
            lines.append(f"Phone: {sale.customer.phone}")
            lines.append("-" * 40)

        lines.append("ITEMS:")
        for item in sale.items.all():
            product_name = item.product.name if item.product else item.part.name
            lines.append(f"{product_name}")
            lines.append(
                f"  {item.quantity} x {item.unit_price_uzs:,.2f} = {item.line_total_uzs:,.2f} UZS"
            )

        lines.append("-" * 40)
        lines.append(f"Subtotal: {sale.subtotal_uzs:,.2f} UZS")
        if sale.discount_value > 0:
            lines.append(f"Discount: -{sale.discount_value:,.2f}")
        lines.append(f"TOTAL: {sale.total_uzs:,.2f} UZS")
        lines.append(f"Paid: {sale.total_paid_uzs:,.2f} UZS")
        if sale.change_due_uzs > 0:
            lines.append(f"Change: {sale.change_due_uzs:,.2f} UZS")

        lines.append("=" * 40)
        lines.append("Thank you for your business!")
        lines.append("=" * 40)

        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="receipt_{sale.sale_number}.txt"'
        )
        return response

    @extend_schema(
        description="Print receipt in A4 format (PDF)",
        responses={200: {"type": "string", "format": "binary"}},
    )
    @action(detail=True, methods=["get"], url_path="print-receipt/a4")
    def print_a4_receipt(self, request, pk=None):
        """Generate A4 receipt (PDF format)"""
        sale = self.get_object()

        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import (
                SimpleDocTemplate,
                Table,
                TableStyle,
                Paragraph,
                Spacer,
            )
            from reportlab.lib import colors
        except ImportError:
            return Response(
                {"detail": "PDF generation requires reportlab. Install to enable."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Header
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(50, height - 50, "SALES RECEIPT")

        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, height - 80, f"Receipt #: {sale.sale_number}")
        pdf.drawString(
            50, height - 100, f"Date: {sale.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        pdf.drawString(50, height - 120, f"Warehouse: {sale.warehouse.name}")

        if sale.customer:
            pdf.drawString(50, height - 150, f"Customer: {sale.customer.full_name}")
            pdf.drawString(50, height - 170, f"Phone: {sale.customer.phone}")

        # Items table
        y_position = height - 220
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, "Item")
        pdf.drawString(300, y_position, "Qty")
        pdf.drawString(350, y_position, "Price")
        pdf.drawString(450, y_position, "Total")

        y_position -= 20
        pdf.setFont("Helvetica", 10)

        for item in sale.items.all():
            product_name = item.product.name if item.product else item.part.name
            pdf.drawString(50, y_position, product_name[:40])
            pdf.drawString(300, y_position, str(item.quantity))
            pdf.drawString(350, y_position, f"{item.unit_price_uzs:,.2f}")
            pdf.drawString(450, y_position, f"{item.line_total_uzs:,.2f}")
            y_position -= 20

        # Totals
        y_position -= 20
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(350, y_position, "Subtotal:")
        pdf.drawString(450, y_position, f"{sale.subtotal_uzs:,.2f} UZS")

        if sale.discount_value > 0:
            y_position -= 20
            pdf.drawString(350, y_position, "Discount:")
            pdf.drawString(450, y_position, f"-{sale.discount_value:,.2f}")

        y_position -= 20
        pdf.drawString(350, y_position, "TOTAL:")
        pdf.drawString(450, y_position, f"{sale.total_uzs:,.2f} UZS")

        y_position -= 20
        pdf.drawString(350, y_position, "Paid:")
        pdf.drawString(450, y_position, f"{sale.total_paid_uzs:,.2f} UZS")

        if sale.change_due_uzs > 0:
            y_position -= 20
            pdf.drawString(350, y_position, "Change:")
            pdf.drawString(450, y_position, f"{sale.change_due_uzs:,.2f} UZS")

        pdf.save()
        buffer.seek(0)

        response = HttpResponse(buffer.read(), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="receipt_{sale.sale_number}.pdf"'
        )
        return response


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


@extend_schema(tags=["order-list"])
class OrderListViewSet(viewsets.ModelViewSet):
    queryset = OrderList.objects.select_related(
        "product", "part", "warehouse", "supplier", "requested_by"
    ).all()
    serializer_class = OrderListSerializer
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]

    @extend_schema(
        description="Get pending orders (not yet ordered from supplier)",
        responses={200: OrderListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="pending")
    def pending_orders(self, request):
        """Return all pending order requests"""
        pending = self.get_queryset().filter(status=OrderList.Status.PENDING)
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    @extend_schema(
        description="Mark order as ordered (sent to supplier)",
        responses={200: OrderListSerializer},
    )
    @action(detail=True, methods=["post"], url_path="mark-ordered")
    def mark_ordered(self, request, pk=None):
        """Mark an order as ordered"""
        order = self.get_object()
        order.status = OrderList.Status.ORDERED
        order.ordered_at = timezone.now()
        order.save()
        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @extend_schema(
        description="Mark order as received and update stock",
        responses={200: OrderListSerializer},
    )
    @action(detail=True, methods=["post"], url_path="mark-received")
    def mark_received(self, request, pk=None):
        """Mark an order as received and update stock"""
        order = self.get_object()
        quantity_received = request.data.get(
            "quantity_received", order.quantity_requested
        )

        with transaction.atomic():
            order.status = OrderList.Status.RECEIVED
            order.quantity_received = quantity_received
            order.received_at = timezone.now()
            order.save()

            # Create inbound stock movement
            StockMovement.objects.create(
                movement_type=StockMovement.MovementType.INBOUND,
                warehouse_to=order.warehouse,
                product=order.product,
                part=order.part,
                quantity=quantity_received,
                note=f"Order received from {order.supplier.name if order.supplier else 'supplier'}",
            ).apply()

        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @extend_schema(
        description="Generate order list report for printing/sending to supplier",
        responses={200: {"type": "string", "format": "binary"}},
    )
    @action(detail=False, methods=["get"], url_path="print-order-list")
    def print_order_list(self, request):
        """Generate CSV of pending orders"""
        pending_orders = self.get_queryset().filter(status=OrderList.Status.PENDING)

        lines = [
            "Product Code,Product Name,Warehouse,Supplier,Qty Requested,Expected Date,Notes"
        ]
        for order in pending_orders:
            product_code = (
                order.product.code if order.product else f"PART-{order.part_id}"
            )
            product_name = order.product.name if order.product else order.part.name
            supplier_name = order.supplier.name if order.supplier else "N/A"
            expected = (
                order.expected_date.strftime("%Y-%m-%d")
                if order.expected_date
                else "N/A"
            )

            lines.append(
                f'"{product_code}","{product_name}","{order.warehouse.name}",'
                f'"{supplier_name}",{order.quantity_requested},"{expected}","{order.notes}"'
            )

        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="order_list.csv"'
        return response


@extend_schema(tags=["inventory-check"])
class InventoryCheckViewSet(viewsets.ModelViewSet):
    queryset = InventoryCheck.objects.select_related(
        "warehouse", "conducted_by"
    ).prefetch_related("lines__stock__product", "lines__stock__part")
    permission_classes = [BaseAuthPermission, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.WAREHOUSE]

    def get_serializer_class(self):
        if self.action == "create":
            return InventoryCheckWriteSerializer
        return InventoryCheckSerializer

    @extend_schema(responses=InventoryCheckSerializer)
    def create(self, request, *args, **kwargs):
        """Create a new inventory check with lines"""
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        check = serializer.save()
        return Response(
            InventoryCheckSerializer(check).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        description="Get difference report (items with discrepancies)",
        responses={200: InventoryCheckLineSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="difference-report")
    def difference_report(self, request, pk=None):
        """Return lines with differences (actual != expected)"""
        check = self.get_object()
        lines_with_diff = check.lines.exclude(difference=0)
        serializer = InventoryCheckLineSerializer(lines_with_diff, many=True)
        return Response(serializer.data)

    @extend_schema(
        description="Generate printable inventory check report",
        responses={200: {"type": "string", "format": "binary"}},
    )
    @action(detail=True, methods=["get"], url_path="print-report")
    def print_report(self, request, pk=None):
        """Generate CSV report of inventory check"""
        check = self.get_object()

        lines = [
            f"Inventory Check Report: {check.check_number}",
            f"Warehouse: {check.warehouse.name}",
            f"Date: {check.scheduled_date}",
            f"Status: {check.get_status_display()}",
            "",
            "Product Code,Product Name,Expected,Actual,Difference,Notes",
        ]

        for line in check.lines.all():
            product_code = (
                line.stock.product.code
                if line.stock.product
                else f"PART-{line.stock.part_id}"
            )
            product_name = (
                line.stock.product.name if line.stock.product else line.stock.part.name
            )

            lines.append(
                f'"{product_code}","{product_name}",'
                f"{line.expected_quantity},{line.actual_quantity},"
                f'{line.difference},"{line.notes}"'
            )

        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="inventory_check_{check.check_number}.csv"'
        )
        return response

    @extend_schema(
        description="Apply inventory adjustments based on check results",
        responses={200: InventoryCheckSerializer},
    )
    @action(detail=True, methods=["post"], url_path="apply-adjustments")
    def apply_adjustments(self, request, pk=None):
        """Apply stock adjustments based on inventory check differences"""
        check = self.get_object()

        if check.status != InventoryCheck.Status.COMPLETED:
            return Response(
                {"detail": "Can only apply adjustments to completed checks"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for line in check.lines.exclude(difference=0):
                # Update stock to actual count
                stock = line.stock
                stock.quantity = line.actual_quantity
                stock.save()

                # Create stock movement record
                if line.difference > 0:
                    # Surplus - create inbound
                    StockMovement.objects.create(
                        movement_type=StockMovement.MovementType.INBOUND,
                        warehouse_to=stock.warehouse,
                        product=stock.product,
                        part=stock.part,
                        quantity=line.difference,
                        note=f"Inventory adjustment from check {check.check_number}",
                    )
                else:
                    # Shortage - create loss
                    StockMovement.objects.create(
                        movement_type=StockMovement.MovementType.LOSS,
                        warehouse_from=stock.warehouse,
                        product=stock.product,
                        part=stock.part,
                        quantity=abs(line.difference),
                        note=f"Inventory adjustment from check {check.check_number}",
                    )

        serializer = self.get_serializer(check)
        return Response(serializer.data)


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
