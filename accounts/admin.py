from django.contrib import admin
from .models import User, Client, Domain


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = ("username", "email", "role", "is_active", "is_staff")
	list_filter = ("role", "is_active", "is_staff")
	search_fields = ("username", "email")
	ordering = ("username",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
	list_display = ("name", "schema_name", "paid_until", "on_trial")
	search_fields = ("name", "schema_name")


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
	list_display = ("domain", "tenant", "is_primary")
	search_fields = ("domain",)
