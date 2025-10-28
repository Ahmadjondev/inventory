from django.contrib import admin
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
    SaleReturnItem,
    NotificationPreference,
    AuditLog,
    PaymentGatewayTransaction,
    Barcode,
    OfflineSaleBuffer,
    OrderList,
    InventoryCheck,
    InventoryCheckLine,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "created_at")
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "created_at")
    search_fields = ("name", "description")
    list_filter = ("parent",)


class ProductPartInline(admin.TabularInline):
    model = ProductPart
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "supplier",
        "price_usd",
        "price_uzs",
        "usd_to_uzs_rate",
        "is_split",
    )
    search_fields = ("code", "name", "oem_number")
    list_filter = ("category", "supplier", "is_split")
    inlines = [ProductPartInline]


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "created_at")
    search_fields = ("name",)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "product", "part", "quantity", "updated_at")
    list_filter = ("warehouse",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "movement_type",
        "warehouse_from",
        "warehouse_to",
        "product",
        "part",
        "quantity",
        "processed_at",
    )
    list_filter = ("movement_type", "warehouse_from", "warehouse_to")
    search_fields = ("note",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "loyalty_points")
    search_fields = ("first_name", "last_name", "phone")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate_number", "customer", "make", "model")
    search_fields = ("plate_number", "customer__first_name", "customer__last_name")


@admin.register(LoyaltyLedger)
class LoyaltyLedgerAdmin(admin.ModelAdmin):
    list_display = ("customer", "entry_type", "points", "created_at")
    list_filter = ("entry_type",)


@admin.register(ServiceCatalog)
class ServiceCatalogAdmin(admin.ModelAdmin):
    list_display = ("name", "default_price_uzs", "default_price_usd")
    search_fields = ("name",)


class ServiceOrderLineInline(admin.TabularInline):
    model = ServiceOrderLine
    extra = 0


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "status", "total_uzs", "opened_at")
    list_filter = ("status",)
    search_fields = ("number", "customer__first_name", "customer__last_name")
    inlines = [ServiceOrderLineInline]


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("category", "amount_uzs", "incurred_on", "payment_type")
    list_filter = ("payment_type", "category")


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "account_type", "balance_uzs", "due_date")
    list_filter = ("account_type",)
    search_fields = ("name",)


@admin.register(CreditEntry)
class CreditEntryAdmin(admin.ModelAdmin):
    list_display = ("account", "direction", "amount_uzs", "due_date", "is_settled")
    list_filter = ("direction", "is_settled")


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("effective_date", "usd_to_uzs", "source")
    search_fields = ("source",)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


class SalePaymentInline(admin.TabularInline):
    model = SalePayment
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "sale_number",
        "warehouse",
        "customer",
        "total_uzs",
        "status",
        "completed_at",
    )
    list_filter = ("status", "warehouse")
    search_fields = ("sale_number", "customer__first_name", "customer__last_name")
    inlines = [SaleItemInline, SalePaymentInline]


class SaleReturnItemInline(admin.TabularInline):
    model = SaleReturnItem
    extra = 0


@admin.register(SaleReturn)
class SaleReturnAdmin(admin.ModelAdmin):
    list_display = (
        "return_number",
        "sale",
        "status",
        "total_refunded_uzs",
        "processed_at",
    )
    list_filter = ("status",)
    inlines = [SaleReturnItemInline]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("customer", "notify_sms", "notify_telegram")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_model", "created_at")
    search_fields = ("action", "target_model")


@admin.register(PaymentGatewayTransaction)
class PaymentGatewayTransactionAdmin(admin.ModelAdmin):
    list_display = ("sale", "provider", "status", "amount_uzs", "created_at")
    list_filter = ("provider", "status")


@admin.register(Barcode)
class BarcodeAdmin(admin.ModelAdmin):
    list_display = ("code", "product", "label_type", "is_primary")
    search_fields = ("code", "product__name")


@admin.register(OfflineSaleBuffer)
class OfflineSaleBufferAdmin(admin.ModelAdmin):
    list_display = ("device_id", "synced", "created_at")
    list_filter = ("synced",)


@admin.register(OrderList)
class OrderListAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "part",
        "warehouse",
        "supplier",
        "quantity_requested",
        "quantity_received",
        "status",
        "expected_date",
        "created_at",
    )
    list_filter = ("status", "warehouse", "supplier")
    search_fields = ("product__name", "product__code", "part__name", "notes")
    date_hierarchy = "created_at"


class InventoryCheckLineInline(admin.TabularInline):
    model = InventoryCheckLine
    extra = 0
    readonly_fields = ("difference",)


@admin.register(InventoryCheck)
class InventoryCheckAdmin(admin.ModelAdmin):
    list_display = (
        "check_number",
        "warehouse",
        "status",
        "scheduled_date",
        "conducted_by",
        "created_at",
    )
    list_filter = ("status", "warehouse")
    search_fields = ("check_number", "notes")
    date_hierarchy = "scheduled_date"
    inlines = [InventoryCheckLineInline]


@admin.register(InventoryCheckLine)
class InventoryCheckLineAdmin(admin.ModelAdmin):
    list_display = (
        "inventory_check",
        "stock",
        "expected_quantity",
        "actual_quantity",
        "difference",
    )
    list_filter = ("inventory_check__warehouse",)
    readonly_fields = ("difference",)
