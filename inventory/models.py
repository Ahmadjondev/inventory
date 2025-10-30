import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base model adding created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=24, blank=True)

    def __str__(self):
        return self.name


class Category(TimeStampedModel):
    """Product categories for organization and filtering."""

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subcategories",
        help_text="Parent category for hierarchical structure",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    """Represents a purchasable product or assembled item.

    Prices are stored both in USD and UZS – UZS auto-calculated if not provided.
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)
    oem_number = models.CharField(max_length=150, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        help_text="Product category",
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, related_name="products"
    )
    price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    price_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    usd_to_uzs_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="Exchange rate used for conversion",
    )
    is_split = models.BooleanField(default=False, help_text="Has been split into parts")

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["code"])]
        unique_together = [("name", "code")]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProductPart(TimeStampedModel):
    """A logical part derived from a parent product for individual sale."""

    parent = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="parts")
    name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    price_uzs = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.parent.code})"


class Warehouse(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    location = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Stock(TimeStampedModel):
    """Current stock levels per product (or part) per warehouse."""

    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stocks"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stocks", null=True, blank=True
    )
    part = models.ForeignKey(
        ProductPart,
        on_delete=models.CASCADE,
        related_name="stocks",
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(
        default=10, help_text="Alert when stock falls below this level"
    )
    reorder_quantity = models.PositiveIntegerField(
        default=50, help_text="Suggested reorder quantity"
    )

    class Meta:
        unique_together = [("warehouse", "product", "part")]

    @property
    def is_low_stock(self):
        """Check if current quantity is below threshold."""
        return self.quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        """Check if product is out of stock."""
        return self.quantity == 0

    def __str__(self):
        label = self.product.code if self.product else f"PART:{self.part_id}"
        return f"{label} @ {self.warehouse.name}: {self.quantity}"


class StockMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        INBOUND = "in", "Inbound"
        OUTBOUND = "out", "Outbound"
        TRANSFER = "transfer", "Transfer"
        LOSS = "loss", "Loss / Write-off"

    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    warehouse_from = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="movements_out",
        null=True,
        blank=True,
    )
    warehouse_to = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="movements_in",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="movements",
    )
    part = models.ForeignKey(
        ProductPart,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="movements",
    )
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        target = self.product or self.part
        return f"{self.movement_type} {self.quantity} of {target}"

    def apply(self):
        """Apply stock movement effects.
        For transfer: deduct from warehouse_from and add to warehouse_to.
        For inbound: add to warehouse_to.
        For outbound/loss: deduct from warehouse_from.
        """
        item_field = {"product": self.product, "part": self.part}
        if self.movement_type == self.MovementType.TRANSFER:
            if not (self.warehouse_from and self.warehouse_to):
                raise ValueError(
                    "Transfer requires both source and destination warehouses"
                )
            _adjust_stock(self.warehouse_from, -self.quantity, **item_field)
            _adjust_stock(self.warehouse_to, self.quantity, **item_field)
        elif self.movement_type == self.MovementType.INBOUND:
            _adjust_stock(self.warehouse_to, self.quantity, **item_field)
        elif self.movement_type == self.MovementType.OUTBOUND:
            _adjust_stock(self.warehouse_from, -self.quantity, **item_field)
        elif self.movement_type == self.MovementType.LOSS:
            _adjust_stock(self.warehouse_from, -self.quantity, **item_field)
        else:
            raise ValueError("Unknown movement type")


def _adjust_stock(warehouse, delta, product=None, part=None):
    if not warehouse:
        raise ValueError("Warehouse required for stock adjustment")
    stock, _ = Stock.objects.get_or_create(
        warehouse=warehouse, product=product, part=part, defaults={"quantity": 0}
    )
    new_qty = stock.quantity + delta
    if new_qty < 0:
        raise ValueError("Insufficient stock for movement")
    stock.quantity = new_qty
    stock.save(update_fields=["quantity", "updated_at"])


class Customer(TimeStampedModel):
    """End-customer profile for sales and service records."""

    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=24, unique=True)
    notes = models.TextField(blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["first_name", "last_name"]
        indexes = [models.Index(fields=["phone"])]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name or self.phone


class Vehicle(TimeStampedModel):
    """Customer owned vehicles tracked for service history."""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="vehicles"
    )
    plate_number = models.CharField(max_length=15)
    make = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=80, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    vin = models.CharField(max_length=64, blank=True)

    class Meta:
        unique_together = (("customer", "plate_number"),)
        ordering = ["plate_number"]

    def __str__(self):
        return (
            f"{self.plate_number}"
            if not self.make
            else f"{self.plate_number} ({self.make})"
        )


class LoyaltyLedger(TimeStampedModel):
    """Tracks loyalty point adjustments (+/-) per customer."""

    class EntryType(models.TextChoices):
        EARN = "earn", "Earn"
        REDEEM = "redeem", "Redeem"

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="loyalty_ledger"
    )
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    points = models.IntegerField()
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.entry_type} {self.points} for {self.customer}"


class ServiceCatalog(TimeStampedModel):
    """Catalog of services provided by the shop (oil change, filter change, etc)."""

    name = models.CharField(max_length=120, unique=True)
    default_price_uzs = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    default_price_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    default_duration_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ServiceOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        INVOICED = "invoiced", "Invoiced"

    number = models.CharField(max_length=32, unique=True, default="")
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_orders",
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_orders",
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.DRAFT
    )
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    is_complimentary = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    total_uzs = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    linked_sale = models.ForeignKey(
        "Sale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_orders",
    )

    class Meta:
        ordering = ["-opened_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"SO-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.number


class ServiceOrderLine(TimeStampedModel):
    order = models.ForeignKey(
        ServiceOrder, on_delete=models.CASCADE, related_name="lines"
    )
    service = models.ForeignKey(
        ServiceCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_lines",
    )
    description = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    price_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    is_free = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.order.number} - {self.description or self.service}"


class ExpenseCategory(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    color = models.CharField(max_length=7, default="#2c3e50")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Expense(TimeStampedModel):
    class PaymentType(models.TextChoices):
        CASH = "cash", "Cash"
        TRANSFER = "transfer", "Bank transfer"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expenses"
    )
    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_type = models.CharField(max_length=16, choices=PaymentType.choices)
    incurred_on = models.DateField(default=timezone.now)
    paid_to = models.CharField(max_length=255, blank=True)
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_expenses",
    )

    class Meta:
        ordering = ["-incurred_on"]

    def __str__(self):
        return f"{self.category} {self.amount_uzs}"


class CreditAccount(TimeStampedModel):
    class AccountType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        SUPPLIER = "supplier", "Supplier"
        MECHANIC = "mechanic", "Mechanic"

    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    name = models.CharField(max_length=255)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="credit_accounts",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="credit_accounts",
    )
    balance_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    balance_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    credit_limit_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    credit_limit_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.account_type})"


class CreditEntry(TimeStampedModel):
    class EntryDirection(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    account = models.ForeignKey(
        CreditAccount, on_delete=models.CASCADE, related_name="entries"
    )
    direction = models.CharField(max_length=10, choices=EntryDirection.choices)
    amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    amount_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    description = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_settled = models.BooleanField(default=False)
    related_sale = models.ForeignKey(
        "Sale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_entries",
    )

    class Meta:
        ordering = ["-created_at"]

    def apply_to_account(self):
        multiplier = (
            Decimal("1")
            if self.direction == self.EntryDirection.DEBIT
            else Decimal("-1")
        )
        self.account.balance_uzs = (
            self.account.balance_uzs + multiplier * self.amount_uzs
        ).quantize(Decimal("0.01"))
        self.account.balance_usd = (
            self.account.balance_usd + multiplier * self.amount_usd
        ).quantize(Decimal("0.01"))
        self.account.save(update_fields=["balance_uzs", "balance_usd", "updated_at"])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        result = super().save(*args, **kwargs)
        if is_new:
            self.apply_to_account()
        return result

    def __str__(self):
        dir_label = "DR" if self.direction == self.EntryDirection.DEBIT else "CR"
        return f"{dir_label} {self.amount_uzs} for {self.account}"


class ExchangeRate(TimeStampedModel):
    """Daily exchange rate for currency conversions."""

    effective_date = models.DateField(default=timezone.now, unique=True)
    usd_to_uzs = models.DecimalField(max_digits=12, decimal_places=4)
    source = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-effective_date"]

    def __str__(self):
        return f"{self.effective_date}: {self.usd_to_uzs}"


class Sale(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        PARTIALLY_PAID = "partial", "Partially paid"
        PAID = "paid", "Fully paid"
        REFUNDED = "refunded", "Refunded"

    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percent"
        AMOUNT = "amount", "Amount"
        NONE = "none", "No discount"

    sale_number = models.CharField(max_length=32, unique=True, default="")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="sales"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales"
    )
    discount_type = models.CharField(
        max_length=10, choices=DiscountType.choices, default=DiscountType.NONE
    )
    discount_value = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    subtotal_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    subtotal_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    total_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_paid_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    total_paid_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    change_due_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    change_due_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    is_credit_sale = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["sale_number"])]

    def save(self, *args, **kwargs):
        if not self.sale_number:
            self.sale_number = (
                f"S-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
            )
        return super().save(*args, **kwargs)

    @property
    def is_fully_paid(self):
        return self.status == self.Status.PAID

    def recompute_totals(self):
        items = list(self.items.all())
        subtotal_uzs = sum((item.line_total_uzs for item in items), Decimal("0.00"))
        subtotal_usd = sum((item.line_total_usd for item in items), Decimal("0.00"))
        discount_uzs = Decimal("0.00")
        discount_usd = Decimal("0.00")
        if self.discount_type == self.DiscountType.PERCENT:
            discount_uzs = (
                subtotal_uzs * self.discount_value / Decimal("100")
            ).quantize(Decimal("0.01"))
            discount_usd = (
                subtotal_usd * self.discount_value / Decimal("100")
            ).quantize(Decimal("0.01"))
        elif self.discount_type == self.DiscountType.AMOUNT:
            discount_uzs = self.discount_value

        self.subtotal_uzs = subtotal_uzs
        self.subtotal_usd = subtotal_usd
        self.total_uzs = (subtotal_uzs - discount_uzs).quantize(Decimal("0.01"))
        self.total_usd = (subtotal_usd - discount_usd).quantize(Decimal("0.01"))
        payments = list(self.payments.all())
        self.total_paid_uzs = sum((p.amount_uzs for p in payments), Decimal("0.00"))
        self.total_paid_usd = sum((p.amount_usd for p in payments), Decimal("0.00"))
        self.change_due_uzs = max(self.total_paid_uzs - self.total_uzs, Decimal("0.00"))
        self.change_due_usd = max(self.total_paid_usd - self.total_usd, Decimal("0.00"))
        if self.total_paid_uzs >= self.total_uzs:
            self.status = self.Status.PAID
        elif self.total_paid_uzs > 0:
            self.status = self.Status.PARTIALLY_PAID
        else:
            self.status = self.Status.OPEN
        self.save(
            update_fields=[
                "subtotal_uzs",
                "subtotal_usd",
                "total_uzs",
                "total_usd",
                "total_paid_uzs",
                "total_paid_usd",
                "change_due_uzs",
                "change_due_usd",
                "status",
                "updated_at",
            ]
        )

    def finalize(self, actor=None):
        """Finalize sale: persist totals, adjust stock, mark completion."""
        with transaction.atomic():
            self.recompute_totals()
            for item in self.items.select_related("product", "part"):
                StockMovement.objects.create(
                    movement_type=StockMovement.MovementType.OUTBOUND,
                    warehouse_from=self.warehouse,
                    product=item.product,
                    part=item.part,
                    quantity=item.quantity,
                    note=f"Sale {self.sale_number}",
                ).apply()
            self.completed_at = timezone.now()
            self.save(update_fields=["completed_at", "updated_at"])
            if actor:
                AuditLog.objects.create(
                    action="sale_finalized",
                    actor=actor,
                    target_model="Sale",
                    target_id=self.id,
                    context={"sale_number": self.sale_number},
                )

    def __str__(self):
        return self.sale_number


class SaleItem(TimeStampedModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sale_items",
    )
    part = models.ForeignKey(
        ProductPart,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sale_items",
    )
    quantity = models.PositiveIntegerField()
    unit_price_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    unit_price_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    discount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    discount_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    line_total_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    line_total_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        ordering = ["sale", "created_at"]

    def save(self, *args, **kwargs):
        self.line_total_uzs = (
            self.quantity * self.unit_price_uzs - self.discount_uzs
        ).quantize(Decimal("0.01"))
        self.line_total_usd = (
            self.quantity * self.unit_price_usd - self.discount_usd
        ).quantize(Decimal("0.01"))
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sale.sale_number} - {self.product or self.part}"


class SalePayment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        TERMINAL = "terminal", "POS terminal"
        P2P = "p2p", "P2P"
        BANK = "bank", "Bank card"
        OTHER = "other", "Other"

    class Currency(models.TextChoices):
        UZS = "UZS", "UZS"
        USD = "USD", "USD"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=12, choices=Method.choices)
    amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    amount_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.UZS
    )
    paid_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=120, blank=True)
    is_change = models.BooleanField(
        default=False, help_text="Marks change returned to customer"
    )

    class Meta:
        ordering = ["paid_at"]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        result = super().save(*args, **kwargs)
        if is_new:
            self.sale.recompute_totals()
        return result

    def __str__(self):
        return f"{self.method} {self.amount_uzs}"


class SaleReturn(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        COMPLETED = "completed", "Completed"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="returns")
    return_number = models.CharField(max_length=32, unique=True, default="")
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    total_refunded_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    total_refunded_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.return_number:
            self.return_number = (
                f"SR-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
            )
        return super().save(*args, **kwargs)

    def process(self, actor=None):
        if self.status == self.Status.COMPLETED:
            return
        with transaction.atomic():
            total_refund_uzs = Decimal("0.00")
            total_refund_usd = Decimal("0.00")
            for item in self.items.select_related("sale_item"):
                sale_item = item.sale_item
                StockMovement.objects.create(
                    movement_type=StockMovement.MovementType.INBOUND,
                    warehouse_to=self.sale.warehouse,
                    product=sale_item.product,
                    part=sale_item.part,
                    quantity=item.quantity,
                    note=f"Return {self.return_number}",
                ).apply()
                total_refund_uzs += item.refund_amount_uzs
                total_refund_usd += item.refund_amount_usd
            self.total_refunded_uzs = total_refund_uzs
            self.total_refunded_usd = total_refund_usd
            self.status = self.Status.COMPLETED
            self.processed_at = timezone.now()
            self.save(
                update_fields=[
                    "total_refunded_uzs",
                    "total_refunded_usd",
                    "status",
                    "processed_at",
                    "updated_at",
                ]
            )
            self.sale.status = Sale.Status.REFUNDED
            self.sale.save(update_fields=["status", "updated_at"])
            if actor:
                AuditLog.objects.create(
                    action="sale_return_processed",
                    actor=actor,
                    target_model="SaleReturn",
                    target_id=self.id,
                    context={"return_number": self.return_number},
                )

    def __str__(self):
        return self.return_number


class SaleReturnItem(TimeStampedModel):
    sale_return = models.ForeignKey(
        SaleReturn, on_delete=models.CASCADE, related_name="items"
    )
    sale_item = models.ForeignKey(
        SaleItem, on_delete=models.CASCADE, related_name="return_items"
    )
    quantity = models.PositiveIntegerField()
    refund_amount_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    refund_amount_usd = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        ordering = ["sale_return", "created_at"]

    def __str__(self):
        return f"{self.sale_return.return_number} item"


class NotificationPreference(TimeStampedModel):
    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    notify_sms = models.BooleanField(default=False)
    notify_telegram = models.BooleanField(default=False)
    telegram_chat_id = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return f"Notifications for {self.customer}"


class AuditLog(TimeStampedModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64)
    target_model = models.CharField(max_length=64, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} by {self.actor}"


class PaymentGatewayTransaction(TimeStampedModel):
    class Provider(models.TextChoices):
        PAYME = "payme", "Payme"
        CLICK = "click", "Click"
        UZCARD = "uzcard", "UZCARD"
        HUMO = "humo", "HUMO"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name="gateway_transactions"
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    external_id = models.CharField(max_length=120, blank=True)
    amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    response_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider} {self.status}"


class Barcode(TimeStampedModel):
    class LabelType(models.TextChoices):
        EAN13 = "EAN13", "EAN13"
        QR = "QR", "QR"
        CODE128 = "CODE128", "Code 128"

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="barcodes"
    )
    code = models.CharField(max_length=64, unique=True)
    is_primary = models.BooleanField(default=False)
    label_type = models.CharField(
        max_length=16, choices=LabelType.choices, default=LabelType.EAN13
    )

    class Meta:
        ordering = ["product", "-is_primary"]

    def __str__(self):
        return self.code


class OfflineSaleBuffer(TimeStampedModel):
    """Stores offline POS transactions awaiting sync."""

    device_id = models.CharField(max_length=64)
    payload = models.JSONField()
    synced = models.BooleanField(default=False)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def mark_synced(self):
        self.synced = True
        self.synced_at = timezone.now()
        self.save(update_fields=["synced", "synced_at", "updated_at"])


class OrderList(TimeStampedModel):
    """Track unavailable products that need to be ordered from suppliers."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ORDERED = "ordered", "Ordered"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="order_requests",
    )
    part = models.ForeignKey(
        ProductPart,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="order_requests",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="order_requests"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_requests",
    )
    quantity_requested = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_requests",
    )
    notes = models.TextField(blank=True)
    expected_date = models.DateField(null=True, blank=True)
    ordered_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        item = self.product or self.part
        return f"Order {item} x{self.quantity_requested} - {self.status}"


class InventoryCheck(TimeStampedModel):
    """Physical inventory count verification."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    check_number = models.CharField(max_length=32, unique=True, default="")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="inventory_checks"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    scheduled_date = models.DateField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_checks",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.check_number:
            self.check_number = (
                f"IC-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
            )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.check_number} - {self.warehouse.name}"


class InventoryCheckLine(TimeStampedModel):
    """Individual product counts during inventory check."""

    inventory_check = models.ForeignKey(
        InventoryCheck, on_delete=models.CASCADE, related_name="lines"
    )
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="checks")
    expected_quantity = models.PositiveIntegerField(
        help_text="System recorded quantity"
    )
    actual_quantity = models.PositiveIntegerField(help_text="Physical count quantity")
    difference = models.IntegerField(
        default=0, help_text="Actual - Expected (positive=surplus, negative=shortage)"
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["inventory_check", "created_at"]
        unique_together = [("inventory_check", "stock")]

    def save(self, *args, **kwargs):
        self.difference = self.actual_quantity - self.expected_quantity
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.inventory_check.check_number} - {self.stock} (Diff: {self.difference})"
