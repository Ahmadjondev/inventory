from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers
from .models import (
	Product,
	ProductPart,
	Warehouse,
	StockMovement,
	Supplier,
	Stock,
)


class SupplierSerializer(serializers.ModelSerializer):
	class Meta:
		model = Supplier
		fields = ["id", "name", "contact", "created_at", "updated_at"]
		read_only_fields = ["id", "created_at", "updated_at"]


class ProductPartSerializer(serializers.ModelSerializer):
	class Meta:
		model = ProductPart
		fields = [
			"id",
			"parent",
			"name",
			"quantity",
			"price_usd",
			"price_uzs",
			"created_at",
			"updated_at",
		]
		read_only_fields = ["id", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
	parts = ProductPartSerializer(many=True, read_only=True)
	supplier_name = serializers.CharField(source="supplier.name", read_only=True)

	class Meta:
		model = Product
		fields = [
			"id",
			"name",
			"code",
			"oem_number",
			"supplier",
			"supplier_name",
			"price_usd",
			"price_uzs",
			"usd_to_uzs_rate",
			"is_split",
			"parts",
			"created_at",
			"updated_at",
		]
		read_only_fields = ["id", "is_split", "created_at", "updated_at"]

	def validate(self, attrs):
		price_usd = attrs.get("price_usd")
		price_uzs = attrs.get("price_uzs")
		rate = attrs.get("usd_to_uzs_rate")
		if price_usd is not None and rate is not None and not price_uzs:
			attrs["price_uzs"] = (price_usd * rate).quantize(
				Decimal("0.01"), rounding=ROUND_HALF_UP
			)
		return attrs


class WarehouseSerializer(serializers.ModelSerializer):
	class Meta:
		model = Warehouse
		fields = ["id", "name", "location", "created_at", "updated_at"]
		read_only_fields = ["id", "created_at", "updated_at"]


class StockSerializer(serializers.ModelSerializer):
	product_code = serializers.CharField(source="product.code", read_only=True)
	part_name = serializers.CharField(source="part.name", read_only=True)
	warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

	class Meta:
		model = Stock
		fields = [
			"id",
			"warehouse",
			"warehouse_name",
			"product",
			"product_code",
			"part",
			"part_name",
			"quantity",
			"updated_at",
		]
		read_only_fields = ["id", "updated_at"]


class StockMovementSerializer(serializers.ModelSerializer):
	class Meta:
		model = StockMovement
		fields = [
			"id",
			"movement_type",
			"warehouse_from",
			"warehouse_to",
			"product",
			"part",
			"quantity",
			"note",
			"processed_at",
			"created_at",
		]
		read_only_fields = ["id", "created_at"]

	def validate(self, attrs):
		mtype = attrs.get("movement_type")
		wf = attrs.get("warehouse_from")
		wt = attrs.get("warehouse_to")
		if mtype == StockMovement.MovementType.TRANSFER and (not wf or not wt):
			raise serializers.ValidationError(
				"Transfer requires warehouse_from and warehouse_to"
			)
		if mtype in [StockMovement.MovementType.OUTBOUND, StockMovement.MovementType.LOSS] and not wf:
			raise serializers.ValidationError(
				"Outbound/Loss requires warehouse_from"
			)
		if mtype == StockMovement.MovementType.INBOUND and not wt:
			raise serializers.ValidationError("Inbound requires warehouse_to")
		return attrs

	def create(self, validated_data):
		movement = super().create(validated_data)
		movement.apply()
		return movement


class ProductSplitPartInputSerializer(serializers.Serializer):
	name = serializers.CharField(max_length=255)
	quantity = serializers.IntegerField(min_value=1)
	price_usd = serializers.DecimalField(max_digits=12, decimal_places=2)
	price_uzs = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)


class ProductSplitSerializer(serializers.Serializer):
	parts = ProductSplitPartInputSerializer(many=True)

	def validate(self, attrs):
		if not attrs.get("parts"):
			raise serializers.ValidationError("At least one part is required")
		return attrs

	def create(self, validated_data):
		product = self.context["product"]
		if product.is_split:
			raise serializers.ValidationError("Product already split")
		parts_data = validated_data["parts"]
		part_objs = []
		for p in parts_data:
			if not p.get("price_uzs"):
				# derive from product's rate if present
				rate = product.usd_to_uzs_rate
				p["price_uzs"] = (p["price_usd"] * rate).quantize(
					Decimal("0.01"), rounding=ROUND_HALF_UP
				)
			part_objs.append(
				ProductPart.objects.create(
					parent=product,
					name=p["name"],
					quantity=p["quantity"],
					price_usd=p["price_usd"],
					price_uzs=p["price_uzs"],
				)
			)
		product.is_split = True
		product.save(update_fields=["is_split", "updated_at"])
		return part_objs

