from django.db import models
from django.contrib.auth.models import AbstractUser
from django_tenants.models import TenantMixin, DomainMixin
from django.conf import settings
from decimal import Decimal
from django.utils import timezone

# Create your models here.


class Client(TenantMixin):
    """
    Tenant model representing a store/branch in the multi-tenant system.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        TRIAL = "trial", "Trial"
        EXPIRED = "expired", "Expired"

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=500, blank=True)
    phone = models.CharField(max_length=24, blank=True)
    email = models.EmailField(blank=True)

    # Subscription-related fields
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TRIAL
    )
    paid_until = models.DateField(null=True, blank=True)
    on_trial = models.BooleanField(default=True)
    trial_ends_at = models.DateField(null=True, blank=True)

    # Settings
    max_users = models.PositiveIntegerField(default=5)
    max_products = models.PositiveIntegerField(default=1000)
    max_warehouses = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    auto_create_schema = (
        True  # Automatically create PostgreSQL schema on tenant creation
    )
    auto_drop_schema = (
        False  # Do not automatically drop PostgreSQL schema on tenant deletion
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"


class Domain(DomainMixin):
    pass


class User(AbstractUser):
    class Roles(models.TextChoices):
        SUPERADMIN = "superadmin", "SuperAdmin"
        ADMIN = "admin", "Admin"
        CASHIER = "cashier", "Cashier"
        WAREHOUSE = "warehouse", "Warehouse"
        ACCOUNTANT = "accountant", "Accountant"

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.CASHIER,
        help_text="Application role controlling access level",
    )
    phone = models.CharField(max_length=24, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["role"]),
        ]


class SubscriptionPlan(models.Model):
    """
    Subscription plans available for tenants (Basic, Pro, Enterprise).
    """

    class PlanType(models.TextChoices):
        BASIC = "basic", "Basic"
        PRO = "pro", "Pro"
        ENTERPRISE = "enterprise", "Enterprise"

    name = models.CharField(max_length=100, unique=True)
    plan_type = models.CharField(max_length=20, choices=PlanType.choices, unique=True)
    description = models.TextField(blank=True)

    # Pricing
    price_monthly = models.DecimalField(max_digits=12, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=12, decimal_places=2)

    # Limits
    max_users = models.PositiveIntegerField(default=5)
    max_products = models.PositiveIntegerField(default=1000)
    max_warehouses = models.PositiveIntegerField(default=1)
    max_branches = models.PositiveIntegerField(default=1)

    # Features
    has_advanced_reporting = models.BooleanField(default=False)
    has_api_access = models.BooleanField(default=False)
    has_multi_currency = models.BooleanField(default=True)
    has_customer_management = models.BooleanField(default=True)
    has_offline_support = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.price_monthly}/mo"

    class Meta:
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"


class Subscription(models.Model):
    """
    Active subscription for a tenant.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        PENDING = "pending", "Pending"

    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    tenant = models.OneToOneField(
        Client, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    billing_cycle = models.CharField(
        max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY
    )

    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    auto_renew = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name}"

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"


class Invoice(models.Model):
    """
    Billing invoices for subscriptions.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="invoices"
    )
    invoice_number = models.CharField(max_length=50, unique=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.subscription.tenant.name}"

    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        ordering = ["-created_at"]


class Payment(models.Model):
    """
    Payment records for invoices and subscriptions.
    """

    class Provider(models.TextChoices):
        PAYME = "payme", "Payme"
        CLICK = "click", "Click"
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"
        UZCARD = "uzcard", "UZCARD"
        HUMO = "humo", "HUMO"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="payments"
    )

    provider = models.CharField(max_length=20, choices=Provider.choices)
    transaction_id = models.CharField(max_length=255, unique=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    processed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_id} - {self.provider} - {self.amount}"

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]


class Announcement(models.Model):
    """
    Platform-wide announcements from SuperAdmin.
    """

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    title = models.CharField(max_length=255)
    content = models.TextField()
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )

    is_active = models.BooleanField(default=True)

    # Target tenants (empty = all tenants)
    target_tenants = models.ManyToManyField(
        Client, blank=True, related_name="announcements"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_announcements",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ["-created_at"]


class SupportTicket(models.Model):
    """
    Support tickets for tenant issues.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    tenant = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="support_tickets"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    ticket_number = models.CharField(max_length=50, unique=True)
    subject = models.CharField(max_length=255)
    description = models.TextField()

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )

    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticket_number} - {self.subject}"

    class Meta:
        verbose_name = "Support Ticket"
        verbose_name_plural = "Support Tickets"
        ordering = ["-created_at"]


class PlatformAnalytics(models.Model):
    """
    Daily platform analytics snapshot for SuperAdmin dashboard.
    """

    date = models.DateField(unique=True, default=timezone.now)

    total_tenants = models.PositiveIntegerField(default=0)
    active_tenants = models.PositiveIntegerField(default=0)
    trial_tenants = models.PositiveIntegerField(default=0)

    total_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)

    total_revenue = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    monthly_recurring_revenue = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )

    new_signups = models.PositiveIntegerField(default=0)
    cancellations = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Analytics for {self.date}"

    class Meta:
        verbose_name = "Platform Analytics"
        verbose_name_plural = "Platform Analytics"
        ordering = ["-date"]
