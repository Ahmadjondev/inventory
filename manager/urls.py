from django.urls import path
from . import views

app_name = "manager"

urlpatterns = [
    # Authentication
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    # Dashboard (root path, auth required)
    path("", views.dashboard, name="dashboard"),
    # Tenants
    path("tenants/", views.tenant_list, name="tenant_list"),
    path("tenants/create/", views.tenant_create, name="tenant_create"),
    path("tenants/<int:pk>/", views.tenant_detail, name="tenant_detail"),
    path("tenants/<int:pk>/edit/", views.tenant_edit, name="tenant_edit"),
    path("tenants/<int:pk>/delete/", views.tenant_delete, name="tenant_delete"),
    path("tenants/<int:pk>/suspend/", views.tenant_suspend, name="tenant_suspend"),
    path("tenants/<int:pk>/activate/", views.tenant_activate, name="tenant_activate"),
    # Users
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    # Subscription Plans
    path("plans/", views.plan_list, name="plan_list"),
    path("plans/create/", views.plan_create, name="plan_create"),
    path("plans/<int:pk>/edit/", views.plan_edit, name="plan_edit"),
    path("plans/<int:pk>/delete/", views.plan_delete, name="plan_delete"),
    # Subscriptions
    path("subscriptions/", views.subscription_list, name="subscription_list"),
    path(
        "subscriptions/create/", views.subscription_create, name="subscription_create"
    ),
    path(
        "subscriptions/<int:pk>/", views.subscription_detail, name="subscription_detail"
    ),
    path(
        "subscriptions/<int:pk>/edit/",
        views.subscription_edit,
        name="subscription_edit",
    ),
    path(
        "subscriptions/<int:pk>/cancel/",
        views.subscription_cancel,
        name="subscription_cancel",
    ),
    path(
        "subscriptions/<int:pk>/renew/",
        views.subscription_renew,
        name="subscription_renew",
    ),
    path(
        "subscriptions/<int:pk>/change-plan/",
        views.subscription_change_plan,
        name="subscription_change_plan",
    ),
    # Invoices
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    # Payments
    path("payments/", views.payment_list, name="payment_list"),
    path("payments/<int:pk>/", views.payment_detail, name="payment_detail"),
    # Announcements
    path("announcements/", views.announcement_list, name="announcement_list"),
    path(
        "announcements/create/", views.announcement_create, name="announcement_create"
    ),
    path(
        "announcements/<int:pk>/edit/",
        views.announcement_edit,
        name="announcement_edit",
    ),
    path(
        "announcements/<int:pk>/delete/",
        views.announcement_delete,
        name="announcement_delete",
    ),
    # Support Tickets
    path("tickets/", views.ticket_list, name="ticket_list"),
    path("tickets/<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path(
        "tickets/<int:pk>/update-status/",
        views.ticket_update_status,
        name="ticket_update_status",
    ),
    # Analytics
    path("analytics/", views.analytics, name="analytics"),
    # Reports
    path("reports/", views.reports, name="reports"),
]
