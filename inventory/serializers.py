from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from rest_framework import serializers

from .models import (
    Product,
    ProductPart,
    Warehouse,
    StockMovement,
    Supplier,
    Stock,
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
    SaleReturnItem,
    NotificationPreference,
    AuditLog,
    PaymentGatewayTransaction,
    Barcode,
    OfflineSaleBuffer,
)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "contact", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPart
        fields = [
            "id",
            "parent",
            "name",
            "quantity",
            "price_usd",
            "price_uzs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    parts = ProductPartSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "code",
            "oem_number",
            "supplier",
            "supplier_name",
            "price_usd",
            "price_uzs",
            "usd_to_uzs_rate",
            "is_split",
            "parts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_split", "created_at", "updated_at"]

    def validate(self, attrs):
        price_usd = attrs.get("price_usd")
        price_uzs = attrs.get("price_uzs")
        rate = attrs.get("usd_to_uzs_rate")
        if price_usd is not None and rate is not None and not price_uzs:
            attrs["price_uzs"] = (price_usd * rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        return attrs


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "name", "location", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class StockSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    part_name = serializers.CharField(source="part.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = Stock
        fields = [
            "id",
            "warehouse",
            "warehouse_name",
            "product",
            "product_code",
            "part",
            "part_name",
            "quantity",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = [
            "id",
            "movement_type",
            "warehouse_from",
            "warehouse_to",
            "product",
            "part",
            "quantity",
            "note",
            "processed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        mtype = attrs.get("movement_type")
        wf = attrs.get("warehouse_from")
        wt = attrs.get("warehouse_to")
        if mtype == StockMovement.MovementType.TRANSFER and (not wf or not wt):
            raise serializers.ValidationError(
                "Transfer requires warehouse_from and warehouse_to"
            )
        if (
            mtype
            in [StockMovement.MovementType.OUTBOUND, StockMovement.MovementType.LOSS]
            and not wf
        ):
            raise serializers.ValidationError("Outbound/Loss requires warehouse_from")
        if mtype == StockMovement.MovementType.INBOUND and not wt:
            raise serializers.ValidationError("Inbound requires warehouse_to")
        return attrs

    def create(self, validated_data):
        movement = super().create(validated_data)
        movement.apply()
        return movement


class ProductSplitPartInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    quantity = serializers.IntegerField(min_value=1)
    price_usd = serializers.DecimalField(max_digits=12, decimal_places=2)
    price_uzs = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False
    )


class ProductSplitSerializer(serializers.Serializer):
    parts = ProductSplitPartInputSerializer(many=True)

    def validate(self, attrs):
        if not attrs.get("parts"):
            raise serializers.ValidationError("At least one part is required")
        return attrs

    def create(self, validated_data):
        product = self.context["product"]
        if product.is_split:
            raise serializers.ValidationError("Product already split")
        parts_data = validated_data["parts"]
        part_objs = []
        for p in parts_data:
            if not p.get("price_uzs"):
                # derive from product's rate if present
                rate = product.usd_to_uzs_rate
                p["price_uzs"] = (p["price_usd"] * rate).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            part_objs.append(
                ProductPart.objects.create(
                    parent=product,
                    name=p["name"],
                    quantity=p["quantity"],
                    price_usd=p["price_usd"],
                    price_uzs=p["price_uzs"],
                )
            )
        product.is_split = True
        product.save(update_fields=["is_split", "updated_at"])
        return part_objs


class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "email",
            "notes",
            "loyalty_points",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "loyalty_points",
            "created_at",
            "updated_at",
            "full_name",
        ]


class VehicleSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "customer",
            "customer_name",
            "plate_number",
            "make",
            "model",
            "year",
            "vin",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "customer_name"]


class LoyaltyLedgerSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)

    class Meta:
        model = LoyaltyLedger
        fields = [
            "id",
            "customer",
            "customer_name",
            "entry_type",
            "points",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "customer_name", "created_at"]


class ServiceCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCatalog
        fields = [
            "id",
            "name",
            "default_price_uzs",
            "default_price_usd",
            "default_duration_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ServiceOrderLineSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)

    class Meta:
        model = ServiceOrderLine
        fields = [
            "id",
            "order",
            "service",
            "service_name",
            "description",
            "quantity",
            "price_uzs",
            "price_usd",
            "is_free",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "service_name", "created_at", "updated_at", "order"]


class ServiceOrderSerializer(serializers.ModelSerializer):
    lines = ServiceOrderLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)

    class Meta:
        model = ServiceOrder
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "vehicle",
            "vehicle_plate",
            "status",
            "opened_at",
            "closed_at",
            "is_complimentary",
            "note",
            "total_uzs",
            "total_usd",
            "linked_sale",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "number",
            "opened_at",
            "closed_at",
            "total_uzs",
            "total_usd",
            "lines",
            "created_at",
            "updated_at",
            "customer_name",
            "vehicle_plate",
        ]


class ServiceOrderLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOrderLine
        fields = [
            "id",
            "service",
            "description",
            "quantity",
            "price_uzs",
            "price_usd",
            "is_free",
        ]


class ServiceOrderWriteSerializer(serializers.ModelSerializer):
    lines = ServiceOrderLineWriteSerializer(many=True)

    class Meta:
        model = ServiceOrder
        fields = [
            "id",
            "customer",
            "vehicle",
            "status",
            "is_complimentary",
            "note",
            "lines",
        ]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        order = ServiceOrder.objects.create(**validated_data)
        for line in lines_data:
            ServiceOrderLine.objects.create(order=order, **line)
        order.total_uzs = sum(
            (line.price_uzs * line.quantity for line in order.lines.all()),
            Decimal("0.00"),
        )
        order.total_usd = sum(
            (line.price_usd * line.quantity for line in order.lines.all()),
            Decimal("0.00"),
        )
        order.save(update_fields=["total_uzs", "total_usd", "updated_at"])
        return order


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "code", "color", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    recorded_by_username = serializers.CharField(
        source="recorded_by.username", read_only=True
    )

    class Meta:
        model = Expense
        fields = [
            "id",
            "category",
            "category_name",
            "amount_uzs",
            "amount_usd",
            "payment_type",
            "incurred_on",
            "paid_to",
            "note",
            "recorded_by",
            "recorded_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "recorded_by",
            "recorded_by_username",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["recorded_by"] = request.user
        return super().create(validated_data)


class CreditEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditEntry
        fields = [
            "id",
            "account",
            "direction",
            "amount_uzs",
            "amount_usd",
            "description",
            "due_date",
            "is_settled",
            "related_sale",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CreditAccountSerializer(serializers.ModelSerializer):
    entries = CreditEntrySerializer(many=True, read_only=True)

    class Meta:
        model = CreditAccount
        fields = [
            "id",
            "account_type",
            "name",
            "customer",
            "supplier",
            "balance_uzs",
            "balance_usd",
            "credit_limit_uzs",
            "credit_limit_usd",
            "due_date",
            "entries",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "balance_uzs",
            "balance_usd",
            "entries",
            "created_at",
            "updated_at",
        ]


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = [
            "id",
            "effective_date",
            "usd_to_uzs",
            "source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SaleItemSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    part_name = serializers.CharField(source="part.name", read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "sale",
            "product",
            "product_code",
            "product_name",
            "part",
            "part_name",
            "quantity",
            "unit_price_uzs",
            "unit_price_usd",
            "discount_uzs",
            "discount_usd",
            "line_total_uzs",
            "line_total_usd",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "sale",
            "product_code",
            "product_name",
            "part_name",
            "line_total_uzs",
            "line_total_usd",
            "created_at",
            "updated_at",
        ]


class SalePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalePayment
        fields = [
            "id",
            "sale",
            "method",
            "amount_uzs",
            "amount_usd",
            "currency",
            "paid_at",
            "reference",
            "is_change",
            "created_at",
        ]
        read_only_fields = ["id", "sale", "created_at"]


class SaleItemWriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False
    )
    part = serializers.PrimaryKeyRelatedField(
        queryset=ProductPart.objects.all(), required=False
    )
    quantity = serializers.IntegerField(min_value=1)
    unit_price_uzs = serializers.DecimalField(max_digits=18, decimal_places=2)
    unit_price_usd = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0.00")
    )
    discount_uzs = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=Decimal("0.00")
    )
    discount_usd = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0.00")
    )

    def validate(self, attrs):
        if not attrs.get("product") and not attrs.get("part"):
            raise serializers.ValidationError(
                "Either product or part must be provided."
            )
        return attrs


class SalePaymentWriteSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=SalePayment.Method.choices)
    amount_uzs = serializers.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    amount_usd = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0.00")
    )
    currency = serializers.ChoiceField(choices=SalePayment.Currency.choices)
    paid_at = serializers.DateTimeField(required=False)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    is_change = serializers.BooleanField(required=False, default=False)


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    payments = SalePaymentSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "sale_number",
            "warehouse",
            "warehouse_name",
            "customer",
            "customer_name",
            "vehicle",
            "discount_type",
            "discount_value",
            "subtotal_uzs",
            "subtotal_usd",
            "total_uzs",
            "total_usd",
            "total_paid_uzs",
            "total_paid_usd",
            "change_due_uzs",
            "change_due_usd",
            "status",
            "is_credit_sale",
            "due_date",
            "note",
            "completed_at",
            "items",
            "payments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "sale_number",
            "subtotal_uzs",
            "subtotal_usd",
            "total_uzs",
            "total_usd",
            "total_paid_uzs",
            "total_paid_usd",
            "change_due_uzs",
            "change_due_usd",
            "status",
            "completed_at",
            "items",
            "payments",
            "created_at",
            "updated_at",
            "warehouse_name",
            "customer_name",
        ]


class SaleWriteSerializer(serializers.ModelSerializer):
    items = SaleItemWriteSerializer(many=True)
    payments = SalePaymentWriteSerializer(many=True, required=False)

    class Meta:
        model = Sale
        fields = [
            "id",
            "warehouse",
            "customer",
            "vehicle",
            "discount_type",
            "discount_value",
            "is_credit_sale",
            "due_date",
            "note",
            "items",
            "payments",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        payments_data = validated_data.pop("payments", [])
        request = self.context.get("request")
        with transaction.atomic():
            sale = Sale.objects.create(**validated_data)
            for item_data in items_data:
                SaleItem.objects.create(sale=sale, **item_data)
            for payment_data in payments_data:
                SalePayment.objects.create(sale=sale, **payment_data)
            sale.finalize(
                actor=(
                    request.user if request and request.user.is_authenticated else None
                )
            )
        return sale


class SaleReturnItemWriteSerializer(serializers.Serializer):
    sale_item = serializers.PrimaryKeyRelatedField(queryset=SaleItem.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    refund_amount_uzs = serializers.DecimalField(max_digits=18, decimal_places=2)
    refund_amount_usd = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0.00")
    )


class SaleReturnSerializer(serializers.ModelSerializer):
    items = SaleReturnItemWriteSerializer(many=True)
    return_number = serializers.CharField(read_only=True)

    class Meta:
        model = SaleReturn
        fields = [
            "id",
            "sale",
            "return_number",
            "reason",
            "status",
            "items",
            "processed_at",
            "total_refunded_uzs",
            "total_refunded_usd",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "processed_at",
            "total_refunded_uzs",
            "total_refunded_usd",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        request = self.context.get("request")
        with transaction.atomic():
            return_instance = SaleReturn.objects.create(**validated_data)
            for item_data in items_data:
                SaleReturnItem.objects.create(
                    sale_return=return_instance,
                    **item_data,
                )
            return_instance.process(
                actor=(
                    request.user if request and request.user.is_authenticated else None
                )
            )
        return return_instance


class SaleReturnReadItemSerializer(serializers.ModelSerializer):
    sale_item_id = serializers.IntegerField(source="sale_item.id", read_only=True)

    class Meta:
        model = SaleReturnItem
        fields = [
            "id",
            "sale_return",
            "sale_item_id",
            "quantity",
            "refund_amount_uzs",
            "refund_amount_usd",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "sale_return",
            "sale_item_id",
            "created_at",
            "updated_at",
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "customer",
            "notify_sms",
            "notify_telegram",
            "telegram_chat_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_username",
            "action",
            "target_model",
            "target_id",
            "context",
            "created_at",
        ]
        read_only_fields = ["id", "actor", "actor_username", "created_at"]


class PaymentGatewayTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGatewayTransaction
        fields = [
            "id",
            "sale",
            "provider",
            "status",
            "external_id",
            "amount_uzs",
            "response_payload",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class BarcodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barcode
        fields = ["id", "product", "code", "is_primary", "label_type", "created_at"]
        read_only_fields = ["id", "created_at"]


class OfflineSaleBufferSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfflineSaleBuffer
        fields = ["id", "device_id", "payload", "synced", "synced_at", "created_at"]
        read_only_fields = ["id", "synced", "synced_at", "created_at"]
