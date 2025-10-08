from rest_framework import permissions, viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

from accounts.serializers import (
    UserSerializer,
    UserCreateSerializer,
    ClientSerializer,
    ClientCreateSerializer,
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
    SubscriptionCreateSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    PaymentCheckoutSerializer,
    AnnouncementSerializer,
    SupportTicketSerializer,
    SupportTicketCreateSerializer,
    PlatformAnalyticsSerializer,
)
from accounts.models import (
    Client,
    SubscriptionPlan,
    Subscription,
    Invoice,
    Payment,
    Announcement,
    SupportTicket,
    PlatformAnalytics,
)
from .permissions import RolePermission
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import uuid

User = get_user_model()


@extend_schema(tags=["users"])
class UserViewSet(viewsets.ModelViewSet):
    """
    User management endpoints for tenant users.
    Supports CRUD operations with role-based access.
    """

    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, RolePermission]
    allowed_roles = [User.Roles.ADMIN, User.Roles.SUPERADMIN]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    @extend_schema(summary="Get current user profile", responses={200: UserSerializer})
    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def me(self, request):
        """Get the current authenticated user's profile."""
        return Response(self.get_serializer(request.user).data)

    @extend_schema(
        summary="Update user role",
        request={
            "application/json": {
                "type": "object",
                "properties": {"role": {"type": "string"}},
            }
        },
        responses={200: UserSerializer},
    )
    @action(detail=True, methods=["put"], url_path="role")
    def update_role(self, request, pk=None):
        """Update a user's role (Admin/Cashier/Warehouse/Accountant)."""
        user = self.get_object()
        new_role = request.data.get("role")

        if new_role not in dict(User.Roles.choices):
            return Response(
                {"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST
            )

        user.role = new_role
        user.save()
        return Response(self.get_serializer(user).data)


@extend_schema(tags=["tenants"])
class TenantViewSet(viewsets.ModelViewSet):
    """
    Tenant (Store/Branch) management endpoints.
    SuperAdmin only for list/create/delete operations.
    """

    queryset = Client.objects.all().order_by("-created_at")
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return ClientCreateSerializer
        return ClientSerializer

    def get_permissions(self):
        """SuperAdmin required for list/create/delete."""
        if self.action in ["list", "create", "destroy"]:
            return [permissions.IsAuthenticated(), RolePermission()]
        return [permissions.IsAuthenticated()]

    @extend_schema(
        summary="List all tenants",
        description="SuperAdmin only - Returns all tenants in the system",
    )
    def list(self, request, *args, **kwargs):
        # Verify SuperAdmin
        print(request.user.role)
        if request.user.role != User.Roles.SUPERADMIN:
            return Response(
                {"error": "SuperAdmin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create new tenant",
        description="Create a new store/branch tenant with domain",
    )
    def create(self, request, *args, **kwargs):
        if request.user.role != User.Roles.SUPERADMIN:
            return Response(
                {"error": "SuperAdmin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)


@extend_schema(tags=["subscriptions"])
class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Subscription plans (Basic, Pro, Enterprise).
    Read-only for users to view available plans.
    """

    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("price_monthly")
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="List all available subscription plans")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


@extend_schema(tags=["subscriptions"])
class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    Subscription management for tenants.
    Handles subscription creation, upgrades, and cancellations.
    """

    queryset = (
        Subscription.objects.all()
        .select_related("tenant", "plan")
        .order_by("-created_at")
    )
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return SubscriptionCreateSerializer
        return SubscriptionSerializer

    def get_queryset(self):
        """Filter subscriptions based on user role."""
        if self.request.user.role == User.Roles.SUPERADMIN:
            return self.queryset
        # Regular users see only their tenant's subscription
        return self.queryset.filter(tenant__users=self.request.user)

    @extend_schema(
        summary="Upgrade subscription plan",
        request={
            "application/json": {
                "type": "object",
                "properties": {"plan_id": {"type": "integer"}},
            }
        },
        responses={200: SubscriptionSerializer},
    )
    @action(detail=True, methods=["post"])
    def upgrade(self, request, pk=None):
        """Upgrade subscription to a higher plan."""
        subscription = self.get_object()
        new_plan_id = request.data.get("plan_id")

        try:
            new_plan = SubscriptionPlan.objects.get(id=new_plan_id)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {"error": "Plan not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Update subscription
        subscription.plan = new_plan
        # Extend expiry date when plan is changed
        if subscription.expires_at and subscription.expires_at < timezone.now():
            # If expired, set new expiry from now
            if subscription.billing_cycle == Subscription.BillingCycle.MONTHLY:
                subscription.expires_at = timezone.now() + timedelta(days=30)
            else:
                subscription.expires_at = timezone.now() + timedelta(days=365)
        elif subscription.expires_at:
            # If still active, extend from current expiry
            if subscription.billing_cycle == Subscription.BillingCycle.MONTHLY:
                subscription.expires_at = subscription.expires_at + timedelta(days=30)
            else:
                subscription.expires_at = subscription.expires_at + timedelta(days=365)
        else:
            # No expiry set, set from now
            if subscription.billing_cycle == Subscription.BillingCycle.MONTHLY:
                subscription.expires_at = timezone.now() + timedelta(days=30)
            else:
                subscription.expires_at = timezone.now() + timedelta(days=365)

        subscription.status = Subscription.Status.ACTIVE
        subscription.save()

        # Update tenant limits and status
        tenant = subscription.tenant
        tenant.max_users = new_plan.max_users
        tenant.max_products = new_plan.max_products
        tenant.max_warehouses = new_plan.max_warehouses
        tenant.status = Client.Status.ACTIVE
        tenant.paid_until = subscription.expires_at.date()
        tenant.save()

        return Response(self.get_serializer(subscription).data)

    @extend_schema(
        summary="Cancel subscription", responses={200: SubscriptionSerializer}
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a subscription."""
        subscription = self.get_object()
        subscription.status = Subscription.Status.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.auto_renew = False
        subscription.save()

        # Update tenant status
        tenant = subscription.tenant
        tenant.status = Client.Status.SUSPENDED
        tenant.save()

        return Response(self.get_serializer(subscription).data)

    @extend_schema(
        summary="Get subscription invoices",
        responses={200: InvoiceSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def invoices(self, request, pk=None):
        """Get all invoices for a subscription."""
        subscription = self.get_object()
        invoices = subscription.invoices.all()
        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)


@extend_schema(tags=["payments"])
class PaymentViewSet(viewsets.ModelViewSet):
    """
    Payment processing and history.
    Handles payment checkout, callbacks, and history.
    """

    queryset = (
        Payment.objects.all()
        .select_related("subscription", "invoice")
        .order_by("-created_at")
    )
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter payments based on user role."""
        if self.request.user.role == User.Roles.SUPERADMIN:
            return self.queryset
        # Regular users see only their tenant's payments
        return self.queryset.filter(subscription__tenant__users=self.request.user)

    @extend_schema(
        summary="Process payment checkout",
        request=PaymentCheckoutSerializer,
        responses={201: PaymentSerializer},
    )
    @action(detail=False, methods=["post"])
    def checkout(self, request):
        """
        Process payment for a subscription.
        Integrates with Payme, Click, Stripe, PayPal, etc.
        """
        serializer = PaymentCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subscription_id = serializer.validated_data["subscription_id"]
        provider = serializer.validated_data["provider"]
        amount = serializer.validated_data["amount"]
        currency = serializer.validated_data.get("currency", "USD")

        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return Response(
                {"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Create payment record
        payment = Payment.objects.create(
            subscription=subscription,
            provider=provider,
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            amount=amount,
            currency=currency,
            status=Payment.Status.PENDING,
        )

        # Here you would integrate with actual payment providers
        # For now, we'll simulate a successful payment
        payment.status = Payment.Status.COMPLETED
        payment.processed_at = timezone.now()
        payment.save()

        # Update subscription and extend expiry date
        if subscription.expires_at and subscription.expires_at < timezone.now():
            # If expired, set new expiry from now
            if subscription.billing_cycle == Subscription.BillingCycle.MONTHLY:
                subscription.expires_at = timezone.now() + timedelta(days=30)
            else:
                subscription.expires_at = timezone.now() + timedelta(days=365)
        elif subscription.expires_at:
            # If still active, extend from current expiry
            if subscription.billing_cycle == Subscription.BillingCycle.MONTHLY:
                subscription.expires_at = subscription.expires_at + timedelta(days=30)
            else:
                subscription.expires_at = subscription.expires_at + timedelta(days=365)
        else:
            # No expiry set, set from now
            if subscription.billing_cycle == Subscription.BillingCycle.MONTHLY:
                subscription.expires_at = timezone.now() + timedelta(days=30)
            else:
                subscription.expires_at = timezone.now() + timedelta(days=365)

        subscription.status = Subscription.Status.ACTIVE
        subscription.save()

        # Update tenant status and paid_until
        tenant = subscription.tenant
        tenant.status = Client.Status.ACTIVE
        tenant.paid_until = subscription.expires_at.date()
        tenant.save()

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Payment provider callback",
        description="Webhook endpoint for payment provider callbacks",
        request={"application/json": {"type": "object"}},
        responses={200: {"type": "object"}},
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        url_path="callback",
    )
    def callback(self, request):
        """
        Handle payment provider callbacks (webhooks).
        Payme, Click, Stripe, PayPal integration point.
        """
        # Extract provider from request
        provider = request.data.get("provider")
        transaction_id = request.data.get("transaction_id")

        if not transaction_id:
            return Response(
                {"error": "Missing transaction_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Update payment status based on provider response
        payment.provider_response = request.data
        payment.status = Payment.Status.COMPLETED
        payment.processed_at = timezone.now()
        payment.save()

        return Response({"status": "success"})

    @extend_schema(
        summary="Get payment history", responses={200: PaymentSerializer(many=True)}
    )
    @action(detail=False, methods=["get"])
    def history(self, request):
        """Get payment history for current user's tenant."""
        payments = self.get_queryset()
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)


@extend_schema(tags=["platform"])
class PlatformViewSet(viewsets.ViewSet):
    """
    Platform-level endpoints for SuperAdmin.
    Includes analytics, monitoring, announcements, and support tickets.
    """

    permission_classes = [permissions.IsAuthenticated]

    def check_superadmin(self, request):
        """Verify user is SuperAdmin."""
        if request.user.role != User.Roles.SUPERADMIN:
            return Response(
                {"error": "SuperAdmin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @extend_schema(
        summary="Get platform analytics",
        description="Global analytics: tenants, active users, revenue, etc.",
        responses={200: PlatformAnalyticsSerializer},
    )
    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """Get global platform analytics."""
        error = self.check_superadmin(request)
        if error:
            return error

        # Get or create today's analytics
        today = timezone.now().date()
        analytics, created = PlatformAnalytics.objects.get_or_create(
            date=today,
            defaults={
                "total_tenants": Client.objects.count(),
                "active_tenants": Client.objects.filter(
                    status=Client.Status.ACTIVE
                ).count(),
                "trial_tenants": Client.objects.filter(on_trial=True).count(),
                "total_users": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "total_revenue": Payment.objects.filter(
                    status=Payment.Status.COMPLETED
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0,
                "new_signups": Client.objects.filter(created_at__date=today).count(),
            },
        )

        return Response(PlatformAnalyticsSerializer(analytics).data)

    @extend_schema(
        summary="Get system errors and logs",
        description="Platform monitoring and error logs",
        responses={200: {"type": "array", "items": {"type": "object"}}},
    )
    @action(detail=False, methods=["get"])
    def errors(self, request):
        """Get monitoring and error logs."""
        error = self.check_superadmin(request)
        if error:
            return error

        # This would integrate with your logging system
        # For now, return a placeholder
        return Response(
            {
                "message": "Error monitoring endpoint - integrate with logging system",
                "errors": [],
            }
        )


@extend_schema(tags=["platform"])
class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    Platform announcements management.
    SuperAdmin can create announcements for all or specific tenants.
    """

    queryset = Announcement.objects.all().order_by("-created_at")
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter announcements based on user role."""
        if self.request.user.role == User.Roles.SUPERADMIN:
            return self.queryset
        # Regular users see announcements for their tenant
        return self.queryset.filter(
            Q(target_tenants__isnull=True)  # All tenants
            | Q(target_tenants__users=self.request.user)  # Specific tenant
        ).distinct()

    def perform_create(self, serializer):
        """Set created_by to current user."""
        serializer.save(created_by=self.request.user)


@extend_schema(tags=["platform"])
class SupportTicketViewSet(viewsets.ModelViewSet):
    """
    Support ticket management.
    Users can create tickets, SuperAdmin can manage all tickets.
    """

    queryset = (
        SupportTicket.objects.all()
        .select_related("tenant", "created_by", "assigned_to")
        .order_by("-created_at")
    )
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return SupportTicketCreateSerializer
        return SupportTicketSerializer

    def get_queryset(self):
        """Filter tickets based on user role."""
        if self.request.user.role == User.Roles.SUPERADMIN:
            return self.queryset
        # Regular users see only their tenant's tickets
        return self.queryset.filter(tenant__users=self.request.user)

    @extend_schema(
        summary="Assign ticket to support agent",
        request={
            "application/json": {
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
            }
        },
        responses={200: SupportTicketSerializer},
    )
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Assign ticket to a support agent (SuperAdmin only)."""
        if request.user.role != User.Roles.SUPERADMIN:
            return Response(
                {"error": "SuperAdmin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        ticket = self.get_object()
        user_id = request.data.get("user_id")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        ticket.assigned_to = user
        ticket.status = SupportTicket.Status.IN_PROGRESS
        ticket.save()

        return Response(self.get_serializer(ticket).data)

    @extend_schema(
        summary="Resolve support ticket", responses={200: SupportTicketSerializer}
    )
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """Mark ticket as resolved."""
        ticket = self.get_object()
        ticket.status = SupportTicket.Status.RESOLVED
        ticket.resolved_at = timezone.now()
        ticket.save()
        return Response(self.get_serializer(ticket).data)
