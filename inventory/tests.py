from decimal import Decimal
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import (
    Supplier,
    Product,
    Warehouse,
    Stock,
    Sale,
    SaleItem,
    SalePayment,
    SaleReturn,
    SaleReturnItem,
    CreditAccount,
    CreditEntry,
    Customer,
    Vehicle,
    LoyaltyLedger,
    ServiceCatalog,
    ExpenseCategory,
    Expense,
    ExchangeRate,
    NotificationPreference,
    AuditLog,
    PaymentGatewayTransaction,
    Barcode,
    OfflineSaleBuffer,
)


class TenantAwareTestCase(TenantTestCase):
    tenant_schema = "tenant1"
    tenant_domain = "testserver"

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.schema_name = cls.tenant_schema
        tenant.name = "Test Tenant"
        tenant.paid_until = timezone.now().date() + timedelta(days=30)
        tenant.on_trial = False
        tenant.save()

    @classmethod
    def setup_domain(cls, domain):
        domain.domain = cls.tenant_domain
        domain.is_primary = True
        domain.save()


class TenantAwareAPITestCase(TenantAwareTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()


class SaleFlowTests(TenantAwareTestCase):
    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="pass1234",
            role=self.user_model.Roles.ADMIN,
        )
        self.supplier = Supplier.objects.create(name="Supplier A")
        self.warehouse = Warehouse.objects.create(name="Main Warehouse")
        self.product = Product.objects.create(
            name="Oil Filter",
            code="OF-001",
            supplier=self.supplier,
            price_usd=Decimal("10.00"),
            price_uzs=Decimal("120000.00"),
            usd_to_uzs_rate=Decimal("12000.00"),
        )
        Stock.objects.create(warehouse=self.warehouse, product=self.product, quantity=5)

    def _build_sale(self, quantity=2):
        sale = Sale.objects.create(
            warehouse=self.warehouse,
            discount_type=Sale.DiscountType.NONE,
            discount_value=Decimal("0.00"),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=quantity,
            unit_price_uzs=Decimal("120000.00"),
            unit_price_usd=Decimal("10.00"),
        )
        SalePayment.objects.create(
            sale=sale,
            method=SalePayment.Method.CASH,
            amount_uzs=Decimal("120000.00") * quantity,
            currency=SalePayment.Currency.UZS,
        )
        sale.finalize(actor=self.user)
        sale.refresh_from_db()
        return sale

    def test_sale_finalize_deducts_stock_and_marks_paid(self):
        sale = self._build_sale(quantity=2)
        self.assertEqual(sale.total_uzs, Decimal("240000.00"))
        self.assertEqual(sale.status, Sale.Status.PAID)
        stock = Stock.objects.get(warehouse=self.warehouse, product=self.product)
        self.assertEqual(stock.quantity, 3)

    def test_sale_return_restock_and_mark_sale_refunded(self):
        sale = self._build_sale(quantity=1)
        sale_item = sale.items.first()
        sale_return = SaleReturn.objects.create(sale=sale)
        SaleReturnItem.objects.create(
            sale_return=sale_return,
            sale_item=sale_item,
            quantity=1,
            refund_amount_uzs=Decimal("120000.00"),
        )
        sale_return.process(actor=self.user)
        sale.refresh_from_db()
        stock = Stock.objects.get(warehouse=self.warehouse, product=self.product)
        self.assertEqual(stock.quantity, 5)
        self.assertEqual(sale.status, Sale.Status.REFUNDED)

    def test_credit_entry_updates_account_balance(self):
        account = CreditAccount.objects.create(
            account_type=CreditAccount.AccountType.CUSTOMER,
            name="Customer A",
            credit_limit_uzs=Decimal("500000.00"),
        )
        CreditEntry.objects.create(
            account=account,
            direction=CreditEntry.EntryDirection.DEBIT,
            amount_uzs=Decimal("150000.00"),
        )
        account.refresh_from_db()
        self.assertEqual(account.balance_uzs, Decimal("150000.00"))
        CreditEntry.objects.create(
            account=account,
            direction=CreditEntry.EntryDirection.CREDIT,
            amount_uzs=Decimal("50000.00"),
        )
        account.refresh_from_db()
        self.assertEqual(account.balance_uzs, Decimal("100000.00"))


class APITestBase(TenantAwareAPITestCase):
    def setUp(self):
        super().setUp()
        self.User = get_user_model()
        self.admin = self.User.objects.create_user(
            username="api-admin",
            email="api-admin@example.com",
            password="pass1234",
            role=self.User.Roles.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.supplier = Supplier.objects.create(name="Supplier A")
        self.warehouse = Warehouse.objects.create(name="Warehouse A")
        self.product = Product.objects.create(
            name="Brake Pad",
            code="BP-001",
            supplier=self.supplier,
            price_usd=Decimal("15.00"),
            price_uzs=Decimal("180000.00"),
            usd_to_uzs_rate=Decimal("12000.00"),
        )
        Stock.objects.create(
            warehouse=self.warehouse, product=self.product, quantity=10
        )


class SupplierAPITests(APITestBase):
    def test_list_suppliers(self):
        url = reverse("supplier-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_create_supplier(self):
        url = reverse("supplier-list")
        payload = {"name": "Supplier B", "contact": "+99890"}
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Supplier B")


class ProductAPITests(APITestBase):
    def test_list_products(self):
        url = reverse("product-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_create_product(self):
        url = reverse("product-list")
        payload = {
            "name": "Brake Disc",
            "code": "BD-001",
            "supplier": self.supplier.id,
            "price_usd": "20.00",
            "price_uzs": "240000.00",
            "usd_to_uzs_rate": "12000",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["code"], "BD-001")

    def test_split_product(self):
        url = reverse("product-split", args=[self.product.id])
        payload = {
            "parts": [
                {"name": "Pad Left", "quantity": 1, "price_usd": "5.00"},
                {"name": "Pad Right", "quantity": 1, "price_usd": "5.00"},
            ]
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_split)
        self.assertEqual(len(response.data), 2)


class WarehouseAPITests(APITestBase):
    def test_list_warehouses(self):
        url = reverse("warehouse-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_warehouse(self):
        url = reverse("warehouse-list")
        response = self.client.post(url, {"name": "Warehouse B"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class StockAPITests(APITestBase):
    def test_list_stock(self):
        url = reverse("stock-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class StockMovementAPITests(APITestBase):
    def test_create_inbound_movement(self):
        url = reverse("stock-movement-list")
        payload = {
            "movement_type": "in",
            "warehouse_to": self.warehouse.id,
            "product": self.product.id,
            "quantity": 5,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        stock = Stock.objects.get(warehouse=self.warehouse, product=self.product)
        self.assertEqual(stock.quantity, 15)


class CustomerAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            first_name="John", last_name="Doe", phone="+998901234567"
        )

    def test_list_customers(self):
        url = reverse("customer-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_create_customer(self):
        url = reverse("customer-list")
        payload = {
            "first_name": "Alice",
            "last_name": "Smith",
            "phone": "+998901234568",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class VehicleAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            first_name="Driver",
            last_name="One",
            phone="+998901234569",
        )

    def test_create_vehicle(self):
        url = reverse("vehicle-list")
        payload = {
            "customer": self.customer.id,
            "plate_number": "010 AAA",
            "make": "Chevy",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LoyaltyLedgerAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            first_name="Loyal",
            last_name="Customer",
            phone="+998901234570",
        )
        self.ledger = LoyaltyLedger.objects.create(
            customer=self.customer,
            entry_type=LoyaltyLedger.EntryType.EARN,
            points=10,
        )

    def test_list_loyalty_entries(self):
        url = reverse("loyalty-ledger-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)


class ServiceCatalogAPITests(APITestBase):
    def test_create_service(self):
        url = reverse("service-catalog-list")
        payload = {"name": "Oil Change", "default_price_uzs": "150000.00"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class ServiceOrderAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            first_name="Service",
            last_name="User",
            phone="+998901234571",
        )
        self.vehicle = Vehicle.objects.create(
            customer=self.customer,
            plate_number="011 AAA",
            make="Toyota",
        )
        self.service = ServiceCatalog.objects.create(
            name="Diag", default_price_uzs=100000
        )

    def test_create_service_order(self):
        url = reverse("service-order-list")
        payload = {
            "customer": self.customer.id,
            "vehicle": self.vehicle.id,
            "status": "draft",
            "lines": [
                {
                    "service": self.service.id,
                    "description": "Diagnosis",
                    "quantity": 1,
                    "price_uzs": "100000",
                }
            ],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "draft")


class ExpenseAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.category = ExpenseCategory.objects.create(name="Utilities", code="UTIL")

    def test_create_expense_category(self):
        url = reverse("expense-category-list")
        payload = {"name": "Rent", "code": "RENT"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_expense(self):
        url = reverse("expense-list")
        payload = {
            "category": self.category.id,
            "amount_uzs": "500000",
            "payment_type": "cash",
            "incurred_on": timezone.now().date().isoformat(),
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["category"], self.category.id)


class CreditAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.account = CreditAccount.objects.create(
            account_type=CreditAccount.AccountType.CUSTOMER,
            name="Account A",
        )

    def test_create_credit_entry(self):
        url = reverse("credit-entry-list")
        payload = {
            "account": self.account.id,
            "direction": "debit",
            "amount_uzs": "100000.00",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance_uzs, Decimal("100000.00"))


class ExchangeRateAPITests(APITestBase):
    def test_create_exchange_rate(self):
        url = reverse("exchange-rate-list")
        payload = {
            "effective_date": timezone.now().date(),
            "usd_to_uzs": "12750.0000",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class SaleAPITests(APITestBase):
    def test_create_sale(self):
        url = reverse("sale-list")
        payload = {
            "warehouse": self.warehouse.id,
            "discount_type": "none",
            "items": [
                {
                    "product": self.product.id,
                    "quantity": 2,
                    "unit_price_uzs": "180000.00",
                }
            ],
            "payments": [
                {
                    "method": "cash",
                    "amount_uzs": "360000.00",
                    "currency": "UZS",
                }
            ],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "paid")

    def test_finalize_sale(self):
        sale = Sale.objects.create(warehouse=self.warehouse)
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price_uzs=Decimal("180000.00"),
        )
        SalePayment.objects.create(
            sale=sale,
            method=SalePayment.Method.CASH,
            amount_uzs=Decimal("180000.00"),
        )
        url = reverse("sale-finalize", args=[sale.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PAID)


class SaleReturnAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        sale_payload = {
            "warehouse": self.warehouse.id,
            "discount_type": "none",
            "items": [
                {
                    "product": self.product.id,
                    "quantity": 1,
                    "unit_price_uzs": "180000.00",
                }
            ],
            "payments": [
                {
                    "method": "cash",
                    "amount_uzs": "180000.00",
                    "currency": "UZS",
                }
            ],
        }
        sale_response = self.client.post(
            reverse("sale-list"), sale_payload, format="json"
        )
        self.sale_id = sale_response.data["id"]
        self.sale_item_id = sale_response.data["items"][0]["id"]

    def test_create_sale_return(self):
        url = reverse("sale-return-list")
        payload = {
            "sale": self.sale_id,
            "reason": "Defective",
            "items": [
                {
                    "sale_item": self.sale_item_id,
                    "quantity": 1,
                    "refund_amount_uzs": "180000.00",
                }
            ],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "completed")


class NotificationPreferenceAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            first_name="Notify",
            last_name="User",
            phone="+998901234572",
        )

    def test_create_notification_preference(self):
        url = reverse("notification-preference-list")
        payload = {"customer": self.customer.id, "notify_sms": True}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["notify_sms"])


class AuditLogAPITests(APITestBase):
    def test_list_logs(self):
        AuditLog.objects.create(action="test", actor=self.admin)
        url = reverse("audit-log-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PaymentGatewayTransactionAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.sale = Sale.objects.create(warehouse=self.warehouse)

    def test_create_gateway_transaction(self):
        url = reverse("payment-gateway-transaction-list")
        payload = {
            "sale": self.sale.id,
            "provider": "payme",
            "status": "pending",
            "amount_uzs": "100000.00",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class BarcodeAPITests(APITestBase):
    def test_create_barcode(self):
        url = reverse("barcode-list")
        payload = {
            "product": self.product.id,
            "code": "1234567890123",
            "is_primary": True,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_primary"])


class OfflineSaleBufferAPITests(APITestBase):
    def test_create_buffer(self):
        url = reverse("offline-sale-list")
        payload = {
            "device_id": "device-1",
            "payload": {"sale": 1},
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        buffer = OfflineSaleBuffer.objects.get(pk=response.data["id"])
        self.assertFalse(buffer.synced)


class ReportingAPITests(APITestBase):
    def test_report_list(self):
        url = reverse("report-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sales", response.data)

    def test_export_excel(self):
        url = reverse("report-export-excel")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")

    @mock.patch("inventory.views.importlib.import_module")
    def test_export_pdf_missing_dependency(self, import_mock):
        import_mock.side_effect = ModuleNotFoundError()
        url = reverse("report-export-pdf")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)


class UserAPITests(APITestBase):
    def test_me_endpoint(self):
        url = reverse("user-me")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "api-admin")


class PermissionTests(APITestBase):
    def test_access_forbidden_for_wrong_role(self):
        accountant = self.User.objects.create_user(
            username="accountant",
            password="pass1234",
            role=self.User.Roles.ACCOUNTANT,
        )
        client = APIClient()
        client.force_authenticate(accountant)
        url = reverse("product-list")
        response = client.post(
            url,
            {
                "name": "Forbidden Product",
                "code": "FB-001",
                "supplier": self.supplier.id,
                "price_usd": "1.00",
                "price_uzs": "12000.00",
                "usd_to_uzs_rate": "12000",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class JWTAuthTests(TenantAwareAPITestCase):
    def setUp(self):
        super().setUp()
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="jwt-user",
            email="jwt@example.com",
            password="pass1234",
            role=self.User.Roles.ADMIN,
        )

    def test_obtain_and_refresh_token(self):
        obtain_url = reverse("token_obtain_pair")
        response = self.client.post(
            obtain_url, {"username": "jwt-user", "password": "pass1234"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access = response.data["access"]
        refresh = response.data["refresh"]

        refresh_url = reverse("token_refresh")
        refresh_response = self.client.post(refresh_url, {"refresh": refresh})
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)


class ReportCachingTests(APITestBase):
    def test_report_calculations_with_sales(self):
        sale = Sale.objects.create(
            warehouse=self.warehouse,
            created_at=timezone.now() - timedelta(days=1),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price_uzs=Decimal("180000.00"),
        )
        SalePayment.objects.create(
            sale=sale,
            method=SalePayment.Method.CASH,
            amount_uzs=Decimal("180000.00"),
        )
        sale.finalize(actor=self.admin)

        url = reverse("report-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["sales"]["daily"], 0)
