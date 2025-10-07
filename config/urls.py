"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.conf.urls.static import static
from django.http import HttpResponseNotFound
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from accounts.views import UserViewSet
from config import settings
from inventory.views import (
    SupplierViewSet,
    CategoryViewSet,
    ProductViewSet,
    WarehouseViewSet,
    StockViewSet,
    StockMovementViewSet,
    CustomerViewSet,
    VehicleViewSet,
    LoyaltyLedgerViewSet,
    ServiceCatalogViewSet,
    ServiceOrderViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    CreditAccountViewSet,
    CreditEntryViewSet,
    ExchangeRateViewSet,
    SaleViewSet,
    SaleReturnViewSet,
    NotificationPreferenceViewSet,
    AuditLogViewSet,
    PaymentGatewayTransactionViewSet,
    BarcodeViewSet,
    OfflineSaleBufferViewSet,
    ReportingViewSet,
    OrderListViewSet,
    InventoryCheckViewSet,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"stocks", StockViewSet, basename="stock")
router.register(r"stock-movements", StockMovementViewSet, basename="stock-movement")
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"vehicles", VehicleViewSet, basename="vehicle")
router.register(r"loyalty-ledger", LoyaltyLedgerViewSet, basename="loyalty-ledger")
router.register(r"service-catalog", ServiceCatalogViewSet, basename="service-catalog")
router.register(r"service-orders", ServiceOrderViewSet, basename="service-order")
router.register(
    r"expense-categories", ExpenseCategoryViewSet, basename="expense-category"
)
router.register(r"expenses", ExpenseViewSet, basename="expense")
router.register(r"credit-accounts", CreditAccountViewSet, basename="credit-account")
router.register(r"credit-entries", CreditEntryViewSet, basename="credit-entry")
router.register(r"exchange-rates", ExchangeRateViewSet, basename="exchange-rate")
router.register(r"sales", SaleViewSet, basename="sale")
router.register(r"sale-returns", SaleReturnViewSet, basename="sale-return")
router.register(
    r"notification-preferences",
    NotificationPreferenceViewSet,
    basename="notification-preference",
)
router.register(r"audit-logs", AuditLogViewSet, basename="audit-log")
router.register(
    r"payment-transactions",
    PaymentGatewayTransactionViewSet,
    basename="payment-transaction",
)
router.register(r"barcodes", BarcodeViewSet, basename="barcode")
router.register(r"offline-sales", OfflineSaleBufferViewSet, basename="offline-sale")
router.register(r"order-list", OrderListViewSet, basename="order-list")
router.register(r"inventory-checks", InventoryCheckViewSet, basename="inventory-check")
router.register(r"reports", ReportingViewSet, basename="report")

urlpatterns = [
    # OpenAPI schema & docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include(router.urls)),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


def admin_urls():
    from django.conf import settings
    from django.contrib import admin
    from django.urls import path

    return [
        path("admin/", admin.site.urls),
        path("", include("manager.urls")),
    ]


def handler_forbidden_admin(request):
    return HttpResponseNotFound("Not Found")


urlpatterns += admin_urls()
