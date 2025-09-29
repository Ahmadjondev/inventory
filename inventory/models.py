from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
	"""Abstract base model adding created/updated timestamps."""

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class Supplier(TimeStampedModel):
	name = models.CharField(max_length=255, unique=True)
	contact = models.CharField(max_length=255, blank=True)

	def __str__(self):
		return self.name


class Product(TimeStampedModel):
	"""Represents a purchasable product or assembled item.

	Prices are stored both in USD and UZS – UZS auto-calculated if not provided.
	"""

	name = models.CharField(max_length=255)
	code = models.CharField(max_length=100, unique=True)
	oem_number = models.CharField(max_length=150, blank=True)
	supplier = models.ForeignKey(
		Supplier, on_delete=models.SET_NULL, null=True, related_name="products"
	)
	price_usd = models.DecimalField(max_digits=12, decimal_places=2)
	price_uzs = models.DecimalField(max_digits=18, decimal_places=2)
	usd_to_uzs_rate = models.DecimalField(
		max_digits=12,
		decimal_places=4,
		help_text="Exchange rate used for conversion",
	)
	is_split = models.BooleanField(default=False, help_text="Has been split into parts")

	class Meta:
		ordering = ["name"]
		indexes = [models.Index(fields=["code"])]
		unique_together = [("name", "code")]

	def __str__(self):
		return f"{self.code} - {self.name}"


class ProductPart(TimeStampedModel):
	"""A logical part derived from a parent product for individual sale."""

	parent = models.ForeignKey(
		Product, on_delete=models.CASCADE, related_name="parts"
	)
	name = models.CharField(max_length=255)
	quantity = models.PositiveIntegerField(default=1)
	price_usd = models.DecimalField(max_digits=12, decimal_places=2)
	price_uzs = models.DecimalField(max_digits=18, decimal_places=2)

	class Meta:
		ordering = ["name"]

	def __str__(self):
		return f"{self.name} ({self.parent.code})"


class Warehouse(TimeStampedModel):
	name = models.CharField(max_length=150, unique=True)
	location = models.CharField(max_length=255, blank=True)

	def __str__(self):
		return self.name


class Stock(TimeStampedModel):
	"""Current stock levels per product (or part) per warehouse."""

	warehouse = models.ForeignKey(
		Warehouse, on_delete=models.CASCADE, related_name="stocks"
	)
	product = models.ForeignKey(
		Product, on_delete=models.CASCADE, related_name="stocks", null=True, blank=True
	)
	part = models.ForeignKey(
		ProductPart,
		on_delete=models.CASCADE,
		related_name="stocks",
		null=True,
		blank=True,
	)
	quantity = models.PositiveIntegerField(default=0)

	class Meta:
		unique_together = [("warehouse", "product", "part")]

	def __str__(self):
		label = self.product.code if self.product else f"PART:{self.part_id}"
		return f"{label} @ {self.warehouse.name}: {self.quantity}"


class StockMovement(TimeStampedModel):
	class MovementType(models.TextChoices):
		INBOUND = "in", "Inbound"
		OUTBOUND = "out", "Outbound"
		TRANSFER = "transfer", "Transfer"
		LOSS = "loss", "Loss / Write-off"

	movement_type = models.CharField(max_length=20, choices=MovementType.choices)
	warehouse_from = models.ForeignKey(
		Warehouse,
		on_delete=models.CASCADE,
		related_name="movements_out",
		null=True,
		blank=True,
	)
	warehouse_to = models.ForeignKey(
		Warehouse,
		on_delete=models.CASCADE,
		related_name="movements_in",
		null=True,
		blank=True,
	)
	product = models.ForeignKey(
		Product, on_delete=models.CASCADE, null=True, blank=True, related_name="movements"
	)
	part = models.ForeignKey(
		ProductPart,
		on_delete=models.CASCADE,
		null=True,
		blank=True,
		related_name="movements",
	)
	quantity = models.PositiveIntegerField()
	note = models.CharField(max_length=255, blank=True)
	processed_at = models.DateTimeField(default=timezone.now)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		target = self.product or self.part
		return f"{self.movement_type} {self.quantity} of {target}"

	def apply(self):
		"""Apply stock movement effects.
		For transfer: deduct from warehouse_from and add to warehouse_to.
		For inbound: add to warehouse_to.
		For outbound/loss: deduct from warehouse_from.
		"""
		item_field = {"product": self.product, "part": self.part}
		if self.movement_type == self.MovementType.TRANSFER:
			if not (self.warehouse_from and self.warehouse_to):
				raise ValueError("Transfer requires both source and destination warehouses")
			_adjust_stock(self.warehouse_from, -self.quantity, **item_field)
			_adjust_stock(self.warehouse_to, self.quantity, **item_field)
		elif self.movement_type == self.MovementType.INBOUND:
			_adjust_stock(self.warehouse_to, self.quantity, **item_field)
		elif self.movement_type == self.MovementType.OUTBOUND:
			_adjust_stock(self.warehouse_from, -self.quantity, **item_field)
		elif self.movement_type == self.MovementType.LOSS:
			_adjust_stock(self.warehouse_from, -self.quantity, **item_field)
		else:
			raise ValueError("Unknown movement type")


def _adjust_stock(warehouse, delta, product=None, part=None):
	if not warehouse:
		raise ValueError("Warehouse required for stock adjustment")
	stock, _ = Stock.objects.get_or_create(
		warehouse=warehouse, product=product, part=part, defaults={"quantity": 0}
	)
	new_qty = stock.quantity + delta
	if new_qty < 0:
		raise ValueError("Insufficient stock for movement")
	stock.quantity = new_qty
	stock.save(update_fields=["quantity", "updated_at"])

