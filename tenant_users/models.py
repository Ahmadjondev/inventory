from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    User model in SHARED_APPS.
    Since users exist in all schemas, we track which tenant they belong to.
    """

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

    # Track which tenant this user belongs to
    # This is a string field storing the schema_name to avoid circular import
    tenant_schema = models.CharField(
        max_length=63,
        blank=True,
        db_index=True,
        help_text="Schema name of the tenant this user belongs to. Empty for SuperAdmins.",
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["tenant_schema"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["username", "tenant_schema"],
                name="unique_username_per_tenant",
            ),
        ]
