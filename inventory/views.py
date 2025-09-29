from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
	Supplier,
	Product,
	ProductPart,
	Warehouse,
	Stock,
	StockMovement,
)
from .serializers import (
	SupplierSerializer,
	ProductSerializer,
	ProductSplitSerializer,
	ProductPartSerializer,
	WarehouseSerializer,
	StockSerializer,
	StockMovementSerializer,
)
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample


class BaseAuthPermission(permissions.IsAuthenticated):
	pass


@extend_schema(tags=["suppliers"])
class SupplierViewSet(viewsets.ModelViewSet):
	queryset = Supplier.objects.all().order_by("name")
	serializer_class = SupplierSerializer
	permission_classes = [BaseAuthPermission]


@extend_schema(tags=["products"])
class ProductViewSet(viewsets.ModelViewSet):
	queryset = Product.objects.all().order_by("name")
	serializer_class = ProductSerializer
	permission_classes = [BaseAuthPermission]
	lookup_field = "id"

	@extend_schema(
		request=ProductSplitSerializer,
		responses={201: ProductPartSerializer(many=True)},
		examples=[
			OpenApiExample(
				"Split Example",
				value={
					"parts": [
						{"name": "Sub Part A", "quantity": 2, "price_usd": "5.00"},
						{"name": "Sub Part B", "quantity": 1, "price_usd": "10.00"},
					]
				},
			)
		],
		description="Split a product into individually sellable parts. Auto-fills price_uzs if omitted.",
	)
	@action(detail=True, methods=["post"], url_path="split")
	def split(self, request, id=None):
		product = self.get_object()
		serializer = ProductSplitSerializer(data=request.data, context={"product": product})
		serializer.is_valid(raise_exception=True)
		parts = serializer.save()
		return Response(ProductPartSerializer(parts, many=True).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["warehouses"])
class WarehouseViewSet(viewsets.ModelViewSet):
	queryset = Warehouse.objects.all().order_by("name")
	serializer_class = WarehouseSerializer
	permission_classes = [BaseAuthPermission]


@extend_schema(tags=["stocks"])
class StockViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Stock.objects.select_related("warehouse", "product", "part").all()
	serializer_class = StockSerializer
	permission_classes = [BaseAuthPermission]


@extend_schema(tags=["stock-movements"])
class StockMovementViewSet(viewsets.ModelViewSet):
	queryset = StockMovement.objects.select_related(
		"warehouse_from", "warehouse_to", "product", "part"
	).all()
	serializer_class = StockMovementSerializer
	permission_classes = [BaseAuthPermission]
	http_method_names = ["get", "post", "head", "options"]

