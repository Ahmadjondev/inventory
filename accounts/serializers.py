from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
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
from django.utils import timezone
import uuid

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "role",
            "phone",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ["id", "domain", "tenant", "is_primary"]


class ClientSerializer(serializers.ModelSerializer):
    domains = DomainSerializer(many=True, read_only=True)
    subscription_status = serializers.CharField(
        source="subscription.status", read_only=True
    )
    current_plan = serializers.CharField(
        source="subscription.plan.name", read_only=True
    )

    class Meta:
        model = Client
        fields = [
            "id",
            "schema_name",
            "name",
            "address",
            "phone",
            "email",
            "status",
            "paid_until",
            "on_trial",
            "trial_ends_at",
            "max_users",
            "max_products",
            "max_warehouses",
            "created_at",
            "updated_at",
            "domains",
            "subscription_status",
            "current_plan",
        ]
        read_only_fields = ["id", "schema_name", "created_at", "updated_at"]


class ClientCreateSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "address",
            "phone",
            "email",
            "domain",
            "max_users",
            "max_products",
            "max_warehouses",
        ]

    def create(self, validated_data):
        domain_name = validated_data.pop("domain")

        # Generate schema name from tenant name
        schema_name = validated_data["name"].lower().replace(" ", "_").replace("-", "_")
        # Ensure unique schema name
        if Client.objects.filter(schema_name=schema_name).exists():
            schema_name = f"{schema_name}_{uuid.uuid4().hex[:6]}"

        validated_data["schema_name"] = schema_name
        validated_data["on_trial"] = True
        validated_data["status"] = Client.Status.TRIAL

        # Set trial period (30 days)
        from datetime import timedelta

        validated_data["trial_ends_at"] = timezone.now().date() + timedelta(days=30)

        tenant = Client.objects.create(**validated_data)

        # Create domain
        Domain.objects.create(domain=domain_name, tenant=tenant, is_primary=True)

        # Create tenant owner (admin user)
        from django.db import connection

        # Switch to tenant schema to create the user
        connection.set_tenant(tenant)

        # Create admin user for the tenant
        owner_username = f"{schema_name}_admin"
        owner_email = validated_data.get("email", f"{owner_username}@example.com")

        # Create the owner user
        owner = User.objects.create_user(
            username=owner_username,
            email=owner_email,
            password=User.objects.make_random_password(length=12),
            role=User.Roles.ADMIN,
            first_name="Admin",
            last_name=validated_data["name"],
        )

        # Switch back to public schema
        connection.set_schema_to_public()

        return tenant


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_details = SubscriptionPlanSerializer(source="plan", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "plan",
            "plan_details",
            "status",
            "billing_cycle",
            "started_at",
            "expires_at",
            "cancelled_at",
            "auto_renew",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = [
            "id",
            "tenant",
            "plan",
            "billing_cycle",
            "auto_renew",
        ]

    def create(self, validated_data):
        from datetime import timedelta

        subscription = Subscription.objects.create(**validated_data)

        # Set expiration based on billing cycle
        if subscription.billing_cycle == Subscription.BillingCycle.MONTHLY:
            subscription.expires_at = timezone.now() + timedelta(days=30)
        else:
            subscription.expires_at = timezone.now() + timedelta(days=365)

        subscription.save()

        # Update tenant status
        tenant = subscription.tenant
        tenant.status = Client.Status.ACTIVE
        tenant.on_trial = False
        tenant.paid_until = subscription.expires_at.date()
        tenant.save()

        return subscription


class InvoiceSerializer(serializers.ModelSerializer):
    subscription_details = SubscriptionSerializer(source="subscription", read_only=True)
    tenant_name = serializers.CharField(
        source="subscription.tenant.name", read_only=True
    )

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = ["id", "invoice_number", "created_at", "updated_at"]


class PaymentSerializer(serializers.ModelSerializer):
    invoice_details = InvoiceSerializer(source="invoice", read_only=True)

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class PaymentCheckoutSerializer(serializers.Serializer):
    subscription_id = serializers.IntegerField(required=True)
    provider = serializers.ChoiceField(choices=Payment.Provider.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3, default="USD")
    return_url = serializers.URLField(required=False)


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )
    target_tenant_count = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = "__all__"
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_target_tenant_count(self, obj):
        return obj.target_tenants.count()


class SupportTicketSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )
    assigned_to_name = serializers.CharField(
        source="assigned_to.username", read_only=True
    )

    class Meta:
        model = SupportTicket
        fields = "__all__"
        read_only_fields = ["id", "ticket_number", "created_at", "updated_at"]


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["id", "tenant", "subject", "description", "priority"]

    def create(self, validated_data):
        # Generate ticket number
        ticket_number = f"TKT-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        validated_data["ticket_number"] = ticket_number
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class PlatformAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAnalytics
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
