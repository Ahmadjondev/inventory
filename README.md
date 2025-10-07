# 🏪 Multi-Tenant SaaS POS System

A comprehensive, production-ready Point of Sale (POS) system built with Django REST Framework, featuring multi-tenancy, subscription management, and complete inventory control.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Django](https://img.shields.io/badge/Django-5.2+-green)
![DRF](https://img.shields.io/badge/DRF-3.16+-orange)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue)
![License](https://img.shields.io/badge/License-Proprietary-red)

## ✨ Features

### 🏢 Multi-Tenant Architecture
- **Schema-based isolation** using PostgreSQL schemas
- **Domain-based routing** for tenant identification
- **Automatic schema creation** for new tenants
- **Data isolation** ensuring tenant security

### 💳 Subscription & Billing
- **Three-tier plans**: Basic, Pro, Enterprise
- **Flexible billing**: Monthly or yearly cycles
- **Trial periods**: 30-day default trial
- **Automated invoicing** with payment tracking
- **Plan upgrades/downgrades** with proration

### 💰 Payment Processing
Integrated support for multiple payment gateways:
- **Payme** (Uzbekistan)
- **Click** (Uzbekistan)
- **UZCARD** (Uzbekistan)
- **HUMO** (Uzbekistan)
- **Stripe** (International)
- **PayPal** (International)

### 👥 User Management & RBAC
Role-based access control with five distinct roles:
- **SuperAdmin**: Platform administration
- **Admin**: Full tenant access
- **Cashier**: Sales operations
- **Warehouse**: Inventory management
- **Accountant**: Financial operations

### 📦 Inventory Management
- Product catalog with OEM numbers
- Product splitting into parts
- Multi-warehouse support
- Stock movements (in/out/transfer/loss)
- Low stock alerts
- Barcode support (EAN13, QR, Code128)
- Supplier management

### 🛒 Sales & POS
- Intuitive POS interface
- Multiple discount types (percent/amount)
- Mixed payment methods
- Multi-currency (USD, UZS)
- Sale returns and refunds
- Payment gateway integration
- Receipt generation

### 👤 Customer Management
- Customer profiles with CRM
- Vehicle tracking per customer
- Loyalty points system
- Purchase history
- Service history tracking
- Notification preferences (SMS, Telegram)

### 🔧 Service Management
- Service catalog
- Service orders with workflow
- Vehicle service history
- Complimentary service tracking

### 💸 Financial Management
- Expense tracking by category
- Credit account management
- Multi-currency support
- Exchange rate management
- Balance tracking

### 📊 Reporting & Analytics
- Sales reports (daily/monthly/yearly)
- Inventory reports
- Revenue analytics
- Expense breakdowns
- Customer analytics
- Platform-wide metrics (SuperAdmin)

### 🌐 Platform Administration
- Global analytics dashboard
- Announcement system
- Support ticket management
- Error monitoring
- User activity auditing

### 📴 Offline Support
- Offline sale buffering
- Automatic sync when online
- PWA-ready architecture

## 🚀 Quick Start

```bash
# Clone the repository
cd /Users/ahmadjondev/BackendProjects/inventory

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup database
python manage.py migrate_schemas --shared
python manage.py migrate_schemas

# Create subscription plans
python manage.py create_subscription_plans

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver
```

Visit http://localhost:8000/api/docs/ for interactive API documentation.

**📖 For detailed setup instructions, see [QUICK_START.md](QUICK_START.md)**

## 📚 Documentation

- **[Quick Start Guide](QUICK_START.md)** - Get up and running in minutes
- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - Technical overview
- **[API Examples](api_examples.py)** - Working code examples

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer                        │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────┐
│              Django Application Server                   │
│  ┌─────────────────────────────────────────────────┐   │
│  │         django-tenants Middleware               │   │
│  │  (Routes requests to correct schema)            │   │
│  └─────────────────────┬───────────────────────────┘   │
│                        │                                 │
│  ┌────────────────────┴──────────────────────────┐     │
│  │         Django REST Framework                  │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐   │     │
│  │  │ Accounts │  │Inventory │  │ Payments │   │     │
│  │  │   API    │  │   API    │  │   API    │   │     │
│  │  └──────────┘  └──────────┘  └──────────┘   │     │
│  └────────────────────────────────────────────────┘     │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────┐
│            PostgreSQL Database (15+)                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Public Schema (Shared)                         │   │
│  │  - Tenants, Users, Subscriptions, Payments      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Tenant Schema 1 (Store A)                      │   │
│  │  - Products, Sales, Customers, Services         │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Tenant Schema 2 (Store B)                      │   │
│  │  - Products, Sales, Customers, Services         │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 🎯 API Endpoints

### 🔐 Authentication
- `POST /api/auth/token/` - Get JWT token
- `POST /api/auth/token/refresh/` - Refresh token

### 🏢 Tenants
- `POST /api/tenants/` - Create tenant
- `GET /api/tenants/` - List tenants (SuperAdmin)
- `GET /api/tenants/{id}/` - Tenant details
- `PUT /api/tenants/{id}/` - Update tenant
- `DELETE /api/tenants/{id}/` - Delete tenant

### 💳 Subscriptions
- `GET /api/subscriptions/plans/` - List plans
- `POST /api/subscriptions/` - Create subscription
- `POST /api/subscriptions/{id}/upgrade/` - Upgrade plan
- `POST /api/subscriptions/{id}/cancel/` - Cancel
- `GET /api/subscriptions/{id}/invoices/` - Invoices

### 💰 Payments
- `POST /api/payments/checkout/` - Process payment
- `GET /api/payments/history/` - Payment history
- `POST /api/payments/callback/` - Provider webhook

### 👥 Users
- `GET /api/users/me/` - Current user
- `POST /api/users/` - Create user
- `PUT /api/users/{id}/role/` - Update role

### 📦 Inventory
- Full CRUD for: Suppliers, Products, Warehouses, Stocks
- `POST /api/products/{id}/split/` - Split product
- `GET /api/stocks/low-stock/` - Low stock alerts
- Stock movements tracking

### 🛒 Sales
- `POST /api/sales/` - Create sale
- `POST /api/sales/{id}/finalize/` - Finalize sale
- `POST /api/sale-returns/` - Process return

### 📊 Platform (SuperAdmin)
- `GET /api/platform/analytics/` - Global metrics
- `GET /api/platform/announcements/` - Announcements
- `GET /api/platform/support-tickets/` - Support tickets

**Total: 100+ endpoints** - See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete reference.

## 💻 Technology Stack

| Technology | Purpose |
|------------|---------|
| **Django 5.2** | Web framework |
| **Django REST Framework 3.16** | API framework |
| **django-tenants 3.8** | Multi-tenancy |
| **PostgreSQL 15+** | Database |
| **JWT** | Authentication |
| **drf-spectacular** | API documentation |
| **Docker** | Containerization |

## 📊 Subscription Plans

| Feature | Basic | Pro | Enterprise |
|---------|-------|-----|------------|
| **Monthly Price** | $29.99 | $79.99 | $199.99 |
| **Yearly Price** | $299.99 | $799.99 | $1,999.99 |
| **Max Users** | 3 | 10 | 50 |
| **Max Products** | 500 | 5,000 | 50,000 |
| **Warehouses** | 1 | 3 | 10 |
| **Branches** | 1 | 3 | 10 |
| **Advanced Reports** | ❌ | ✅ | ✅ |
| **API Access** | ❌ | ✅ | ✅ |
| **Offline Support** | ❌ | ✅ | ✅ |

## 🐳 Docker Deployment

```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate_schemas --shared
docker-compose exec web python manage.py migrate_schemas

# Create subscription plans
docker-compose exec web python manage.py create_subscription_plans

# Create superuser
docker-compose exec web python manage.py createsuperuser

# View logs
docker-compose logs -f web
```

## 🧪 Testing

```bash
# Run tests
python manage.py test

# Run with coverage
coverage run manage.py test
coverage report

# Test API with example script
python api_examples.py
```

## 🔒 Security Features

- ✅ JWT-based authentication
- ✅ Role-based access control (RBAC)
- ✅ Per-tenant data isolation
- ✅ SQL injection protection (Django ORM)
- ✅ CSRF protection
- ✅ Secure password hashing (PBKDF2)
- ✅ Environment-based secrets (.env)

## 📈 Performance Optimization

- ✅ Database indexing on key fields
- ✅ Query optimization with `select_related`/`prefetch_related`
- ✅ Pagination on all list endpoints
- ✅ Efficient database schema design
- ⏳ Caching layer (Redis recommended)
- ⏳ Async task processing (Celery recommended)

## 🌍 Internationalization

- ✅ Multi-currency support (USD, UZS)
- ✅ Exchange rate management
- ⏳ Multi-language UI (i18n ready)

## 📱 Mobile & Offline

- ✅ RESTful API for mobile apps
- ✅ Offline sale buffering
- ✅ JWT authentication for mobile
- ⏳ React Native/Flutter mobile app
- ⏳ Progressive Web App (PWA)

## 🛣️ Roadmap

### Phase 1: Foundation ✅ (Current)
- ✅ Multi-tenant architecture
- ✅ Subscription & billing
- ✅ Payment gateways
- ✅ Core POS features
- ✅ User management & RBAC

### Phase 2: Enhancement (Q1 2026)
- [ ] Email notifications
- [ ] SMS integration
- [ ] Telegram bot
- [ ] Advanced analytics dashboard
- [ ] PDF/Excel export

### Phase 3: Scale (Q2 2026)
- [ ] Mobile apps (iOS/Android)
- [ ] Progressive Web App
- [ ] Real-time notifications (WebSocket)
- [ ] API rate limiting
- [ ] Two-factor authentication

### Phase 4: Enterprise (Q3 2026)
- [ ] Multi-language support
- [ ] Custom branding per tenant
- [ ] Advanced reporting engine
- [ ] Third-party integrations
- [ ] Automated backups

## 🤝 Contributing

This is a proprietary project. For internal development:

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Submit a pull request

## 📄 License

Proprietary - All rights reserved

## 👨‍💻 Author

**Ahmadjon**
- Project: Multi-Tenant SaaS POS System
- Built with: Django REST Framework
- Date: October 2025

## 📞 Support

For support requests:
1. Create a ticket via API: `POST /api/platform/support-tickets/`
2. Contact the development team
3. Check documentation: `/api/docs/`

## 🙏 Acknowledgments

- Django community
- Django REST Framework
- django-tenants contributors
- PostgreSQL team

---

**⭐ Star this project if you find it useful!**

Made with ❤️ using Django REST Framework
