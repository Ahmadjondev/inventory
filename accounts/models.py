from django.db import models
from django.contrib.auth.models import AbstractUser
from django_tenants.models import TenantMixin, DomainMixin

# Create your models here.

class Client(TenantMixin):
    name = models.CharField(max_length=100)
    paid_until = models.DateField(null=True, blank=True)
    on_trial = models.BooleanField(default=True)

    auto_create_schema = True

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        CASHIER = "cashier", "Cashier"
        STOREKEEPER = "storekeeper", "Storekeeper"
        ACCOUNTANT = "accountant", "Accountant"

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.CASHIER,
        help_text="Application role controlling access level",
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["role"]),
        ]
