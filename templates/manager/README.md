# Manager Templates - File Organization

This directory contains all templates for the admin/manager panel with an optimized folder structure.

## Access

The admin panel is accessible at the **root path (/)** on the admin subdomain:
- **URL**: `admin.localhost:8000/` or `admin.yourdomain.com/`
- **Authentication**: Required (superadmin role only)
- **Entry Point**: Dashboard at root path

## Directory Structure

```
templates/manager/
├── README.md                 # This file
├── base.html                 # Base template for all pages
├── analytics.html            # Platform analytics page
├── reports.html              # Reports page
│
├── announcements/            # Announcement management templates
│   ├── announcement_list.html
│   ├── announcement_form.html
│   └── announcement_confirm_delete.html
│'
├── dashboard/                # Dashboard templates
│   └── dashboard.html        # Main entry point
│
├── invoices/                 # Invoice management templates
│   ├── invoice_list.html
│   └── invoice_detail.html
│
├── payments/                 # Payment management templates
│   ├── payment_list.html
│   └── payment_detail.html
│
├── plans/                    # Subscription plan templates
│   ├── plan_list.html
│   ├── plan_form.html
│   ├── plan_confirm_delete.html
│   ├── subscription_list.html
│   └── subscription_detail.html
│
├── tenants/                  # Tenant management templates
│   ├── tenant_list.html
│   ├── tenant_detail.html
│   ├── tenant_form.html
│   └── tenant_confirm_delete.html
│
├── tickets/                  # Support ticket templates
│   ├── ticket_list.html
│   └── ticket_detail.html
│
└── users/                    # User management templates
    ├── user_list.html
    ├── user_detail.html
    ├── user_form.html
    └── user_confirm_delete.html
```

## Template Naming Conventions

### List Views
- `{model}_list.html` - Lists all items with filtering/pagination

### Detail Views
- `{model}_detail.html` - Shows detailed information for a single item

### Forms
- `{model}_form.html` - Create/Edit form (handles both operations)

### Delete Confirmations
- `{model}_confirm_delete.html` - Confirmation page before deletion

## Base Templates

- **base.html**: Main layout with sidebar navigation, top bar, and content area
- **landing.html**: Public landing page for admin subdomain

## Template Inheritance

All templates extend `manager/base.html` which provides:
- Responsive navigation sidebar
- Top navigation bar with user info
- Flash message display
- Alpine.js for interactivity
- Tailwind CSS for styling
- Font Awesome icons

## Usage in Views

Template paths are referenced relative to the templates directory:

```python
# Example
return render(request, "manager/tenants/tenant_list.html", context)
```

## Benefits of This Structure

1. **Better Organization**: Related templates are grouped together
2. **Easier Navigation**: Clear folder names indicate content
3. **Scalability**: Easy to add new templates to appropriate folders
4. **Maintainability**: Reduces clutter in main directory
5. **Team Collaboration**: Clear structure helps team members find files quickly

## Future Additions

When adding new templates:
1. Create a new folder if it represents a new feature area
2. Follow the naming conventions above
3. Update this README if adding a new folder
4. Ensure views.py references the correct template path
