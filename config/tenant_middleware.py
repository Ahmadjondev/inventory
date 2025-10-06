"""
Custom tenant middleware that works with admin subdomain.
"""

from django_tenants.middleware.main import TenantMainMiddleware as BaseTenantMiddleware
from django.db import connection
from django_tenants.utils import get_public_schema_name
from django.conf import settings


class CustomTenantMiddleware(BaseTenantMiddleware):
    """
    Custom wrapper around TenantMainMiddleware that respects the skip_tenant_check flag.

    If AdminSubdomainMiddleware has set skip_tenant_check=True on the request,
    this middleware will use the public schema instead of trying to resolve a tenant.

    Also bypasses tenant resolution for static and media files.
    """

    def process_request(self, request):
        """
        Check if we should skip tenant resolution.
        Skip for: admin subdomain, static files, media files.
        """
        # Skip tenant resolution for static and media files
        path = request.path_info
        if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
            # Use public schema for static/media files
            schema_name = get_public_schema_name()
            connection.set_schema(schema_name)

            # Create a proper mock tenant
            class PublicTenant:
                schema_name = get_public_schema_name()
                domain_url = request.get_host()

                def __str__(self):
                    return "Public Schema"

            request.tenant = PublicTenant()
            return None

        # Check if AdminSubdomainMiddleware marked this request to skip tenant checks
        if getattr(request, "skip_tenant_check", False):
            # Use public schema for admin subdomain
            schema_name = get_public_schema_name()
            connection.set_schema(schema_name)

            # Set a proper mock tenant object with required attributes
            # This prevents errors in code that expects request.tenant
            class PublicTenant:
                schema_name = get_public_schema_name()
                domain_url = request.get_host()
                id = None

                def __str__(self):
                    return "Public Schema (Admin Subdomain)"

            request.tenant = PublicTenant()
            return None

        # Normal tenant resolution for non-admin subdomains
        return super().process_request(request)
