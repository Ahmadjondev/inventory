from django.contrib import admin
from .models import (
	Supplier,
	Product,
	ProductPart,
	Warehouse,
	Stock,
	StockMovement,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
	list_display = ("name", "contact", "created_at")
	search_fields = ("name",)


class ProductPartInline(admin.TabularInline):
	model = ProductPart
	extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
	list_display = (
		"code",
		"name",
		"supplier",
		"price_usd",
		"price_uzs",
		"usd_to_uzs_rate",
		"is_split",
	)
	search_fields = ("code", "name", "oem_number")
	inlines = [ProductPartInline]


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
	list_display = ("name", "location", "created_at")
	search_fields = ("name",)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
	list_display = ("warehouse", "product", "part", "quantity", "updated_at")
	list_filter = ("warehouse",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
	list_display = (
		"movement_type",
		"warehouse_from",
		"warehouse_to",
		"product",
		"part",
		"quantity",
		"processed_at",
	)
	list_filter = ("movement_type", "warehouse_from", "warehouse_to")
	search_fields = ("note",)

