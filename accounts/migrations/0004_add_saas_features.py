# Generated migration for multi-tenant SaaS features

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        (
            "accounts",
            "0003_rename_accounts_us_role_9d8b2e_idx_accounts_us_role_1fa9a5_idx_and_more",
        ),
    ]

    operations = [
        # Add new fields to Client model
        migrations.AddField(
            model_name="client",
            name="address",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="client",
            name="phone",
            field=models.CharField(blank=True, max_length=24),
        ),
        migrations.AddField(
            model_name="client",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="client",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("suspended", "Suspended"),
                    ("trial", "Trial"),
                    ("expired", "Expired"),
                ],
                default="trial",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="trial_ends_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="max_users",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="client",
            name="max_products",
            field=models.PositiveIntegerField(default=1000),
        ),
        migrations.AddField(
            model_name="client",
            name="max_warehouses",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="client",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="client",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        # Add new role to User model
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("superadmin", "SuperAdmin"),
                    ("admin", "Admin"),
                    ("cashier", "Cashier"),
                    ("warehouse", "Warehouse"),
                    ("accountant", "Accountant"),
                ],
                default="cashier",
                help_text="Application role controlling access level",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="phone",
            field=models.CharField(blank=True, max_length=24),
        ),
        # Create SubscriptionPlan model
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                (
                    "plan_type",
                    models.CharField(
                        choices=[
                            ("basic", "Basic"),
                            ("pro", "Pro"),
                            ("enterprise", "Enterprise"),
                        ],
                        max_length=20,
                        unique=True,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                ("price_monthly", models.DecimalField(decimal_places=2, max_digits=12)),
                ("price_yearly", models.DecimalField(decimal_places=2, max_digits=12)),
                ("max_users", models.PositiveIntegerField(default=5)),
                ("max_products", models.PositiveIntegerField(default=1000)),
                ("max_warehouses", models.PositiveIntegerField(default=1)),
                ("max_branches", models.PositiveIntegerField(default=1)),
                ("has_advanced_reporting", models.BooleanField(default=False)),
                ("has_api_access", models.BooleanField(default=False)),
                ("has_multi_currency", models.BooleanField(default=True)),
                ("has_customer_management", models.BooleanField(default=True)),
                ("has_offline_support", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Subscription Plan",
                "verbose_name_plural": "Subscription Plans",
            },
        ),
        # Create Subscription model
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("cancelled", "Cancelled"),
                            ("expired", "Expired"),
                            ("pending", "Pending"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                (
                    "billing_cycle",
                    models.CharField(
                        choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
                        default="monthly",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("auto_renew", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="accounts.subscriptionplan",
                    ),
                ),
                (
                    "tenant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription",
                        to="accounts.client",
                    ),
                ),
            ],
            options={
                "verbose_name": "Subscription",
                "verbose_name_plural": "Subscriptions",
            },
        ),
        # Create Invoice model
        migrations.CreateModel(
            name="Invoice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("invoice_number", models.CharField(max_length=50, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="USD", max_length=3)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("pending", "Pending"),
                            ("paid", "Paid"),
                            ("failed", "Failed"),
                            ("refunded", "Refunded"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("billing_period_start", models.DateField()),
                ("billing_period_end", models.DateField()),
                ("due_date", models.DateField()),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoices",
                        to="accounts.subscription",
                    ),
                ),
            ],
            options={
                "verbose_name": "Invoice",
                "verbose_name_plural": "Invoices",
                "ordering": ["-created_at"],
            },
        ),
        # Create Payment model
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("payme", "Payme"),
                            ("click", "Click"),
                            ("stripe", "Stripe"),
                            ("paypal", "PayPal"),
                            ("uzcard", "UZCARD"),
                            ("humo", "HUMO"),
                            ("manual", "Manual"),
                        ],
                        max_length=20,
                    ),
                ),
                ("transaction_id", models.CharField(max_length=255, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="USD", max_length=3)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("refunded", "Refunded"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("provider_response", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "invoice",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="accounts.invoice",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="accounts.subscription",
                    ),
                ),
            ],
            options={
                "verbose_name": "Payment",
                "verbose_name_plural": "Payments",
                "ordering": ["-created_at"],
            },
        ),
        # Create Announcement model
        migrations.CreateModel(
            name="Announcement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("low", "Low"),
                            ("medium", "Medium"),
                            ("high", "High"),
                            ("critical", "Critical"),
                        ],
                        default="medium",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_announcements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "target_tenants",
                    models.ManyToManyField(
                        blank=True, related_name="announcements", to="accounts.client"
                    ),
                ),
            ],
            options={
                "verbose_name": "Announcement",
                "verbose_name_plural": "Announcements",
                "ordering": ["-created_at"],
            },
        ),
        # Create SupportTicket model
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ticket_number", models.CharField(max_length=50, unique=True)),
                ("subject", models.CharField(max_length=255)),
                ("description", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("in_progress", "In Progress"),
                            ("resolved", "Resolved"),
                            ("closed", "Closed"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("low", "Low"),
                            ("medium", "Medium"),
                            ("high", "High"),
                            ("urgent", "Urgent"),
                        ],
                        default="medium",
                        max_length=20,
                    ),
                ),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_tickets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_tickets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="support_tickets",
                        to="accounts.client",
                    ),
                ),
            ],
            options={
                "verbose_name": "Support Ticket",
                "verbose_name_plural": "Support Tickets",
                "ordering": ["-created_at"],
            },
        ),
        # Create PlatformAnalytics model
        migrations.CreateModel(
            name="PlatformAnalytics",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "date",
                    models.DateField(default=django.utils.timezone.now, unique=True),
                ),
                ("total_tenants", models.PositiveIntegerField(default=0)),
                ("active_tenants", models.PositiveIntegerField(default=0)),
                ("trial_tenants", models.PositiveIntegerField(default=0)),
                ("total_users", models.PositiveIntegerField(default=0)),
                ("active_users", models.PositiveIntegerField(default=0)),
                (
                    "total_revenue",
                    models.DecimalField(decimal_places=2, default=0, max_digits=18),
                ),
                (
                    "monthly_recurring_revenue",
                    models.DecimalField(decimal_places=2, default=0, max_digits=18),
                ),
                ("new_signups", models.PositiveIntegerField(default=0)),
                ("cancellations", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Platform Analytics",
                "verbose_name_plural": "Platform Analytics",
                "ordering": ["-date"],
            },
        ),
        # Update Client model Meta
        migrations.AlterModelOptions(
            name="client",
            options={"verbose_name": "Tenant", "verbose_name_plural": "Tenants"},
        ),
    ]
