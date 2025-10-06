from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import timedelta, date
from decimal import Decimal

from accounts.models import (
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


def is_superadmin(user):
    """Check if user is superadmin"""
    return user.is_authenticated and user.role == User.Roles.SUPERADMIN


@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    """Main dashboard with key metrics"""
    today = timezone.now().date()

    # Basic counts
    total_tenants = Client.objects.count()
    active_tenants = Client.objects.filter(status=Client.Status.ACTIVE).count()
    trial_tenants = Client.objects.filter(status=Client.Status.TRIAL).count()
    suspended_tenants = Client.objects.filter(status=Client.Status.SUSPENDED).count()

    total_users = User.objects.count()
    total_plans = SubscriptionPlan.objects.filter(is_active=True).count()

    # Revenue metrics
    total_revenue = Payment.objects.filter(status=Payment.Status.COMPLETED).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    monthly_revenue = Payment.objects.filter(
        status=Payment.Status.COMPLETED, created_at__gte=today.replace(day=1)
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    # Recent signups (last 30 days)
    recent_signups = Client.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).count()

    # Recent tenants
    recent_tenants = Client.objects.order_by("-created_at")[:5]

    # Open support tickets
    open_tickets = SupportTicket.objects.filter(
        status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS]
    ).count()

    # Expiring subscriptions (next 7 days)
    expiring_soon = Subscription.objects.filter(
        expires_at__lte=today + timedelta(days=7),
        expires_at__gte=today,
        status=Subscription.Status.ACTIVE,
    ).count()

    # Monthly growth data (last 6 months)
    months_data = []
    for i in range(5, -1, -1):
        month_date = today - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if i > 0:
            next_month = (month_date + timedelta(days=32)).replace(day=1)
        else:
            next_month = today + timedelta(days=1)

        month_tenants = Client.objects.filter(
            created_at__gte=month_start, created_at__lt=next_month
        ).count()

        month_revenue = Payment.objects.filter(
            status=Payment.Status.COMPLETED,
            created_at__gte=month_start,
            created_at__lt=next_month,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        months_data.append(
            {
                "month": month_start.strftime("%b %Y"),
                "tenants": month_tenants,
                "revenue": float(month_revenue),
            }
        )

    context = {
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "trial_tenants": trial_tenants,
        "suspended_tenants": suspended_tenants,
        "total_users": total_users,
        "total_plans": total_plans,
        "total_revenue": total_revenue,
        "monthly_revenue": monthly_revenue,
        "recent_signups": recent_signups,
        "recent_tenants": recent_tenants,
        "open_tickets": open_tickets,
        "expiring_soon": expiring_soon,
        "months_data": months_data,
        "now": timezone.now(),
    }

    return render(request, "manager/dashboard/dashboard.html", context)


@login_required
@user_passes_test(is_superadmin)
def tenant_list(request):
    """List all tenants with filtering"""
    tenants = Client.objects.all().order_by("-created_at")

    # Filtering
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("search", "")

    if status_filter:
        tenants = tenants.filter(status=status_filter)

    if search_query:
        tenants = tenants.filter(
            Q(name__icontains=search_query)
            | Q(schema_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(tenants, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "search_query": search_query,
        "status_choices": Client.Status.choices,
    }

    return render(request, "manager/tenants/tenant_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def tenant_detail(request, pk):
    """View tenant details"""
    tenant = get_object_or_404(Client, pk=pk)

    # Get related data
    domains = tenant.domains.all()
    users = User.objects.filter(groups__name=f"tenant_{tenant.schema_name}")
    subscription = getattr(tenant, "subscription", None)
    recent_invoices = Invoice.objects.filter(subscription__tenant=tenant).order_by(
        "-created_at"
    )[:5]

    context = {
        "tenant": tenant,
        "domains": domains,
        "users": users,
        "subscription": subscription,
        "recent_invoices": recent_invoices,
    }

    return render(request, "manager/tenants/tenant_detail.html", context)


@login_required
@user_passes_test(is_superadmin)
def tenant_create(request):
    """Create new tenant"""
    if request.method == "POST":
        name = request.POST.get("name")
        schema_name = request.POST.get("schema_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        domain_name = request.POST.get("domain")

        try:
            # Create tenant
            tenant = Client.objects.create(
                name=name,
                schema_name=schema_name,
                email=email,
                phone=phone,
                address=address,
            )

            # Create domain
            Domain.objects.create(domain=domain_name, tenant=tenant, is_primary=True)

            messages.success(request, f'Tenant "{name}" created successfully!')
            return redirect("manager:tenant_detail", pk=tenant.pk)
        except Exception as e:
            messages.error(request, f"Error creating tenant: {str(e)}")

    return render(request, "manager/tenants/tenant_form.html", {"action": "Create"})


@login_required
@user_passes_test(is_superadmin)
def tenant_edit(request, pk):
    """Edit tenant"""
    tenant = get_object_or_404(Client, pk=pk)

    if request.method == "POST":
        tenant.name = request.POST.get("name", tenant.name)
        tenant.email = request.POST.get("email", tenant.email)
        tenant.phone = request.POST.get("phone", tenant.phone)
        tenant.address = request.POST.get("address", tenant.address)
        tenant.max_users = int(request.POST.get("max_users", tenant.max_users))
        tenant.max_products = int(request.POST.get("max_products", tenant.max_products))
        tenant.max_warehouses = int(
            request.POST.get("max_warehouses", tenant.max_warehouses)
        )

        try:
            tenant.save()
            messages.success(request, "Tenant updated successfully!")
            return redirect("manager:tenant_detail", pk=tenant.pk)
        except Exception as e:
            messages.error(request, f"Error updating tenant: {str(e)}")

    context = {"tenant": tenant, "action": "Edit"}

    return render(request, "manager/tenants/tenant_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def tenant_delete(request, pk):
    """Delete tenant"""
    tenant = get_object_or_404(Client, pk=pk)

    if request.method == "POST":
        tenant_name = tenant.name
        try:
            tenant.delete()
            messages.success(request, f'Tenant "{tenant_name}" deleted successfully!')
            return redirect("manager:tenant_list")
        except Exception as e:
            messages.error(request, f"Error deleting tenant: {str(e)}")
            return redirect("manager:tenant_detail", pk=pk)

    context = {"tenant": tenant}
    return render(request, "manager/tenants/tenant_confirm_delete.html", context)


@login_required
@user_passes_test(is_superadmin)
def tenant_suspend(request, pk):
    """Suspend tenant"""
    tenant = get_object_or_404(Client, pk=pk)
    tenant.status = Client.Status.SUSPENDED
    tenant.save()
    messages.warning(request, f'Tenant "{tenant.name}" has been suspended.')
    return redirect("manager:tenant_detail", pk=pk)


@login_required
@user_passes_test(is_superadmin)
def tenant_activate(request, pk):
    """Activate tenant"""
    tenant = get_object_or_404(Client, pk=pk)
    tenant.status = Client.Status.ACTIVE
    tenant.save()
    messages.success(request, f'Tenant "{tenant.name}" has been activated.')
    return redirect("manager:tenant_detail", pk=pk)


@login_required
@user_passes_test(is_superadmin)
def user_list(request):
    """List all users"""
    users = User.objects.all().order_by("-date_joined")

    # Filtering
    role_filter = request.GET.get("role", "")
    search_query = request.GET.get("search", "")

    if role_filter:
        users = users.filter(role=role_filter)

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "role_filter": role_filter,
        "search_query": search_query,
        "role_choices": User.Roles.choices,
    }

    return render(request, "manager/users/user_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def user_detail(request, pk):
    """View user details"""
    user = get_object_or_404(User, pk=pk)

    context = {
        "user_obj": user,
    }

    return render(request, "manager/users/user_detail.html", context)


@login_required
@user_passes_test(is_superadmin)
def user_create(request):
    """Create new user"""
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        role = request.POST.get("role")
        phone = request.POST.get("phone")

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=phone,
            )
            messages.success(request, f'User "{username}" created successfully!')
            return redirect("manager:user_detail", pk=user.pk)
        except Exception as e:
            messages.error(request, f"Error creating user: {str(e)}")

    context = {
        "action": "Create",
        "role_choices": User.Roles.choices,
    }

    return render(request, "manager/users/user_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def user_edit(request, pk):
    """Edit user"""
    user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        user.email = request.POST.get("email", user.email)
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.role = request.POST.get("role", user.role)
        user.phone = request.POST.get("phone", user.phone)
        user.is_active = request.POST.get("is_active") == "on"

        password = request.POST.get("password")
        if password:
            user.set_password(password)

        try:
            user.save()
            messages.success(request, "User updated successfully!")
            return redirect("manager:user_detail", pk=user.pk)
        except Exception as e:
            messages.error(request, f"Error updating user: {str(e)}")

    context = {
        "user_obj": user,
        "action": "Edit",
        "role_choices": User.Roles.choices,
    }

    return render(request, "manager/users/user_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def user_delete(request, pk):
    """Delete user"""
    user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        username = user.username
        try:
            user.delete()
            messages.success(request, f'User "{username}" deleted successfully!')
            return redirect("manager:user_list")
        except Exception as e:
            messages.error(request, f"Error deleting user: {str(e)}")
            return redirect("manager:user_detail", pk=pk)

    context = {"user_obj": user}
    return render(request, "manager/users/user_confirm_delete.html", context)


@login_required
@user_passes_test(is_superadmin)
def plan_list(request):
    """List subscription plans"""
    plans = SubscriptionPlan.objects.all().order_by("plan_type")

    context = {"plans": plans}
    return render(request, "manager/plans/plan_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def plan_create(request):
    """Create subscription plan"""
    if request.method == "POST":
        try:
            plan = SubscriptionPlan.objects.create(
                name=request.POST.get("name"),
                plan_type=request.POST.get("plan_type"),
                description=request.POST.get("description"),
                price_monthly=Decimal(request.POST.get("price_monthly")),
                price_yearly=Decimal(request.POST.get("price_yearly")),
                max_users=int(request.POST.get("max_users")),
                max_products=int(request.POST.get("max_products")),
                max_warehouses=int(request.POST.get("max_warehouses")),
                max_branches=int(request.POST.get("max_branches")),
                has_advanced_reporting=request.POST.get("has_advanced_reporting")
                == "on",
                has_api_access=request.POST.get("has_api_access") == "on",
                has_multi_currency=request.POST.get("has_multi_currency") == "on",
                has_offline_support=request.POST.get("has_offline_support") == "on",
            )
            messages.success(request, f'Plan "{plan.name}" created successfully!')
            return redirect("manager:plan_list")
        except Exception as e:
            messages.error(request, f"Error creating plan: {str(e)}")

    context = {
        "action": "Create",
        "plan_type_choices": SubscriptionPlan.PlanType.choices,
    }
    return render(request, "manager/plans/plan_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def plan_edit(request, pk):
    """Edit subscription plan"""
    plan = get_object_or_404(SubscriptionPlan, pk=pk)

    if request.method == "POST":
        try:
            plan.name = request.POST.get("name")
            plan.description = request.POST.get("description")
            plan.price_monthly = Decimal(request.POST.get("price_monthly"))
            plan.price_yearly = Decimal(request.POST.get("price_yearly"))
            plan.max_users = int(request.POST.get("max_users"))
            plan.max_products = int(request.POST.get("max_products"))
            plan.max_warehouses = int(request.POST.get("max_warehouses"))
            plan.max_branches = int(request.POST.get("max_branches"))
            plan.has_advanced_reporting = (
                request.POST.get("has_advanced_reporting") == "on"
            )
            plan.has_api_access = request.POST.get("has_api_access") == "on"
            plan.has_multi_currency = request.POST.get("has_multi_currency") == "on"
            plan.has_offline_support = request.POST.get("has_offline_support") == "on"
            plan.is_active = request.POST.get("is_active") == "on"
            plan.save()

            messages.success(request, f'Plan "{plan.name}" updated successfully!')
            return redirect("manager:plan_list")
        except Exception as e:
            messages.error(request, f"Error updating plan: {str(e)}")

    context = {
        "plan": plan,
        "action": "Edit",
        "plan_type_choices": SubscriptionPlan.PlanType.choices,
    }
    return render(request, "manager/plans/plan_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def plan_delete(request, pk):
    """Delete subscription plan"""
    plan = get_object_or_404(SubscriptionPlan, pk=pk)

    if request.method == "POST":
        plan_name = plan.name
        try:
            plan.delete()
            messages.success(request, f'Plan "{plan_name}" deleted successfully!')
        except Exception as e:
            messages.error(request, f"Error deleting plan: {str(e)}")
        return redirect("manager:plan_list")

    context = {"plan": plan}
    return render(request, "manager/plans/plan_confirm_delete.html", context)


@login_required
@user_passes_test(is_superadmin)
def subscription_list(request):
    """List all subscriptions"""
    subscriptions = Subscription.objects.select_related("tenant", "plan").order_by(
        "-created_at"
    )

    # Filtering
    status_filter = request.GET.get("status", "")
    if status_filter:
        subscriptions = subscriptions.filter(status=status_filter)

    # Pagination
    paginator = Paginator(subscriptions, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "status_choices": Subscription.Status.choices,
    }
    return render(request, "manager/plans/subscription_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def subscription_detail(request, pk):
    """View subscription details"""
    subscription = get_object_or_404(Subscription, pk=pk)
    invoices = subscription.invoices.order_by("-created_at")[:10]
    payments = subscription.payments.order_by("-created_at")[:10]

    context = {
        "subscription": subscription,
        "invoices": invoices,
        "payments": payments,
    }
    return render(request, "manager/plans/subscription_detail.html", context)


@login_required
@user_passes_test(is_superadmin)
def invoice_list(request):
    """List all invoices"""
    invoices = Invoice.objects.select_related(
        "subscription__tenant", "subscription__plan"
    ).order_by("-created_at")

    # Filtering
    status_filter = request.GET.get("status", "")
    if status_filter:
        invoices = invoices.filter(status=status_filter)

    # Pagination
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "status_choices": Invoice.Status.choices,
    }
    return render(request, "manager/invoices/invoice_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def invoice_detail(request, pk):
    """View invoice details"""
    invoice = get_object_or_404(Invoice, pk=pk)
    payments = invoice.payments.order_by("-created_at")

    context = {
        "invoice": invoice,
        "payments": payments,
    }
    return render(request, "manager/invoices/invoice_detail.html", context)


@login_required
@user_passes_test(is_superadmin)
def payment_list(request):
    """List all payments"""
    payments = Payment.objects.select_related(
        "subscription__tenant", "invoice"
    ).order_by("-created_at")

    # Filtering
    status_filter = request.GET.get("status", "")
    provider_filter = request.GET.get("provider", "")

    if status_filter:
        payments = payments.filter(status=status_filter)
    if provider_filter:
        payments = payments.filter(provider=provider_filter)

    # Pagination
    paginator = Paginator(payments, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "provider_filter": provider_filter,
        "status_choices": Payment.Status.choices,
        "provider_choices": Payment.Provider.choices,
    }
    return render(request, "manager/payments/payment_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def payment_detail(request, pk):
    """View payment details"""
    payment = get_object_or_404(Payment, pk=pk)

    context = {"payment": payment}
    return render(request, "manager/payments/payment_detail.html", context)


@login_required
@user_passes_test(is_superadmin)
def announcement_list(request):
    """List all announcements"""
    announcements = Announcement.objects.order_by("-created_at")

    context = {"announcements": announcements}
    return render(request, "manager/announcements/announcement_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def announcement_create(request):
    """Create announcement"""
    if request.method == "POST":
        try:
            announcement = Announcement.objects.create(
                title=request.POST.get("title"),
                content=request.POST.get("content"),
                priority=request.POST.get("priority"),
                is_active=request.POST.get("is_active") == "on",
                created_by=request.user,
            )

            # Add target tenants if specified
            tenant_ids = request.POST.getlist("target_tenants")
            if tenant_ids:
                announcement.target_tenants.set(tenant_ids)

            messages.success(request, "Announcement created successfully!")
            return redirect("manager:announcement_list")
        except Exception as e:
            messages.error(request, f"Error creating announcement: {str(e)}")

    context = {
        "action": "Create",
        "priority_choices": Announcement.Priority.choices,
        "tenants": Client.objects.all(),
    }
    return render(request, "manager/announcements/announcement_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def announcement_edit(request, pk):
    """Edit announcement"""
    announcement = get_object_or_404(Announcement, pk=pk)

    if request.method == "POST":
        try:
            announcement.title = request.POST.get("title")
            announcement.content = request.POST.get("content")
            announcement.priority = request.POST.get("priority")
            announcement.is_active = request.POST.get("is_active") == "on"
            announcement.save()

            # Update target tenants
            tenant_ids = request.POST.getlist("target_tenants")
            announcement.target_tenants.set(tenant_ids if tenant_ids else [])

            messages.success(request, "Announcement updated successfully!")
            return redirect("manager:announcement_list")
        except Exception as e:
            messages.error(request, f"Error updating announcement: {str(e)}")

    context = {
        "announcement": announcement,
        "action": "Edit",
        "priority_choices": Announcement.Priority.choices,
        "tenants": Client.objects.all(),
    }
    return render(request, "manager/announcements/announcement_form.html", context)


@login_required
@user_passes_test(is_superadmin)
def announcement_delete(request, pk):
    """Delete announcement"""
    announcement = get_object_or_404(Announcement, pk=pk)

    if request.method == "POST":
        announcement.delete()
        messages.success(request, "Announcement deleted successfully!")
        return redirect("manager:announcement_list")

    context = {"announcement": announcement}
    return render(
        request, "manager/announcements/announcement_confirm_delete.html", context
    )


@login_required
@user_passes_test(is_superadmin)
def ticket_list(request):
    """List all support tickets"""
    tickets = SupportTicket.objects.select_related(
        "tenant", "created_by", "assigned_to"
    ).order_by("-created_at")

    # Filtering
    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")

    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)

    # Pagination
    paginator = Paginator(tickets, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "status_choices": SupportTicket.Status.choices,
        "priority_choices": SupportTicket.Priority.choices,
    }
    return render(request, "manager/tickets/ticket_list.html", context)


@login_required
@user_passes_test(is_superadmin)
def ticket_detail(request, pk):
    """View ticket details"""
    ticket = get_object_or_404(SupportTicket, pk=pk)

    context = {"ticket": ticket}
    return render(request, "manager/tickets/ticket_detail.html", context)


@login_required
@user_passes_test(is_superadmin)
def ticket_update_status(request, pk):
    """Update ticket status"""
    ticket = get_object_or_404(SupportTicket, pk=pk)

    if request.method == "POST":
        new_status = request.POST.get("status")
        ticket.status = new_status

        if new_status == SupportTicket.Status.RESOLVED:
            ticket.resolved_at = timezone.now()
        elif new_status == SupportTicket.Status.CLOSED:
            ticket.closed_at = timezone.now()

        ticket.save()
        messages.success(request, "Ticket status updated successfully!")

    return redirect("manager:ticket_detail", pk=pk)


@login_required
@user_passes_test(is_superadmin)
def analytics(request):
    """Platform analytics"""
    today = timezone.now().date()

    # Get or create today's analytics
    analytics_data, created = PlatformAnalytics.objects.get_or_create(
        date=today,
        defaults={
            "total_tenants": Client.objects.count(),
            "active_tenants": Client.objects.filter(
                status=Client.Status.ACTIVE
            ).count(),
            "trial_tenants": Client.objects.filter(status=Client.Status.TRIAL).count(),
            "total_users": User.objects.count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "total_revenue": Payment.objects.filter(
                status=Payment.Status.COMPLETED
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00"),
            "new_signups": Client.objects.filter(created_at__date=today).count(),
        },
    )

    # Historical data (last 30 days)
    historical_data = PlatformAnalytics.objects.filter(
        date__gte=today - timedelta(days=30)
    ).order_by("date")

    # Revenue by plan
    revenue_by_plan = (
        Subscription.objects.values("plan__name")
        .annotate(
            total_revenue=Sum(
                "payments__amount", filter=Q(payments__status=Payment.Status.COMPLETED)
            )
        )
        .order_by("-total_revenue")
    )

    # Tenant distribution by status
    tenant_distribution = Client.objects.values("status").annotate(count=Count("id"))

    context = {
        "analytics_data": analytics_data,
        "historical_data": historical_data,
        "revenue_by_plan": revenue_by_plan,
        "tenant_distribution": tenant_distribution,
    }
    return render(request, "manager/analytics.html", context)


@login_required
@user_passes_test(is_superadmin)
def reports(request):
    """Generate various reports"""
    today = timezone.now().date()

    # Date range filters
    start_date = request.GET.get("start_date", today - timedelta(days=30))
    end_date = request.GET.get("end_date", today)

    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    # Revenue report
    revenue_report = Payment.objects.filter(
        status=Payment.Status.COMPLETED,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).aggregate(total=Sum("amount"), count=Count("id"), avg=Avg("amount"))

    # Tenant growth
    tenant_growth = Client.objects.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date
    ).count()

    # Subscription changes
    new_subscriptions = Subscription.objects.filter(
        started_at__date__gte=start_date, started_at__date__lte=end_date
    ).count()

    cancelled_subscriptions = Subscription.objects.filter(
        cancelled_at__date__gte=start_date, cancelled_at__date__lte=end_date
    ).count()

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "revenue_report": revenue_report,
        "tenant_growth": tenant_growth,
        "new_subscriptions": new_subscriptions,
        "cancelled_subscriptions": cancelled_subscriptions,
    }
    return render(request, "manager/reports.html", context)


# =============================================================================
# Authentication Views
# =============================================================================


def login_view(request):
    """Login page for admin panel"""
    from django.contrib.auth import authenticate, login

    if request.user.is_authenticated:
        # Already logged in
        if request.user.role == User.Roles.SUPERADMIN:
            return redirect("manager:dashboard")
        else:
            messages.error(request, "You do not have permission to access this area.")
            from django.contrib.auth import logout

            logout(request)

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == User.Roles.SUPERADMIN:
                login(request, user)
                next_url = request.GET.get("next", "/")
                return redirect(next_url)
            else:
                messages.error(
                    request, "You do not have permission to access this area."
                )
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "manager/login.html")


def logout_view(request):
    """Logout view for admin panel"""
    from django.contrib.auth import logout

    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("manager:login")
