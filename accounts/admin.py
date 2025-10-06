from django.contrib import admin
from .models import User, Client, Domain


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Client,
    Domain,
    SubscriptionPlan,
    Subscription,
    Invoice,
    Payment,
    Announcement,
    SupportTicket,
    PlatformAnalytics,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Custom Fields", {"fields": ("role", "phone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Custom Fields", {"fields": ("role", "phone")}),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "schema_name",
        "status",
        "on_trial",
        "paid_until",
        "created_at",
    )
    list_filter = ("status", "on_trial")
    search_fields = ("name", "schema_name", "email")
    readonly_fields = ("schema_name", "created_at", "updated_at")


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain",)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "plan_type", "price_monthly", "price_yearly", "is_active")
    list_filter = ("plan_type", "is_active")
    search_fields = ("name",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "plan",
        "status",
        "billing_cycle",
        "started_at",
        "expires_at",
    )
    list_filter = ("status", "billing_cycle")
    search_fields = ("tenant__name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "subscription",
        "amount",
        "status",
        "due_date",
        "paid_at",
    )
    list_filter = ("status",)
    search_fields = ("invoice_number", "subscription__tenant__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "provider", "amount", "status", "processed_at")
    list_filter = ("provider", "status")
    search_fields = ("transaction_id", "subscription__tenant__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "priority", "is_active", "created_by", "created_at")
    list_filter = ("priority", "is_active")
    search_fields = ("title", "content")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number",
        "tenant",
        "subject",
        "status",
        "priority",
        "created_at",
    )
    list_filter = ("status", "priority")
    search_fields = ("ticket_number", "subject", "tenant__name")
    readonly_fields = ("ticket_number", "created_at", "updated_at")


@admin.register(PlatformAnalytics)
class PlatformAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "total_tenants",
        "active_tenants",
        "total_users",
        "total_revenue",
    )
    list_filter = ("date",)
    readonly_fields = ("created_at", "updated_at")


# @admin.register(Client)
# class ClientAdmin(admin.ModelAdmin):
# 	list_display = ("name", "schema_name", "paid_until", "on_trial")
# 	search_fields = ("name", "schema_name")


# @admin.register(Domain)
# class DomainAdmin(admin.ModelAdmin):
# 	list_display = ("domain", "tenant", "is_primary")
# 	search_fields = ("domain",)
