from django.utils.deprecation import MiddlewareMixin
from django.http import Http404
from django.shortcuts import redirect
from django.conf import settings


class AdminSubdomainMiddleware(MiddlewareMixin):
    """
    Middleware to handle admin subdomain routing.

    CRITICAL: This middleware MUST be placed BEFORE TenantMainMiddleware in settings.
    It intercepts admin subdomain requests and bypasses tenant resolution entirely.

    For admin subdomain requests:
    - Sets skip_tenant_check flag to bypass TenantMainMiddleware
    - Uses public schema for all database operations
    - Manager admin panel is served at root (/) path

    For tenant subdomain requests:
    - Allows normal tenant resolution
    - Manager admin panel is not accessible

    Examples:
        - admin.localhost:8000 -> Manager Admin Panel (public schema, no tenant)
        - admin.localhost:8000/tenants/ -> Tenant Management
        - tenant1.localhost:8000 -> Tenant App (tenant1 schema)
    """

    def process_request(self, request):
        """
        Check if this is an admin subdomain request.
        If yes, mark it to bypass tenant resolution.
        If no, block /manager/ access.
        """
        # Always allow static and media files to pass through
        path = request.path_info
        if path.startswith(settings.STATIC_URL) or path.startswith(
            getattr(settings, "MEDIA_URL", "/media/")
        ):
            request.skip_tenant_check = True
            return None

        host = request.get_host().split(":")[0]  # Remove port
        host_parts = host.split(".")

        # Check if the subdomain is 'admin'
        if len(host_parts) >= 2 and host_parts[0].lower() == "admin":
            # Mark as admin subdomain - this signals to skip tenant middleware
            request.is_admin_subdomain = True
            request.skip_tenant_check = True

            # Admin subdomain - allow all manager paths
            # No redirect needed as manager URLs are at root

            # Allow request to proceed without tenant resolution
            return None
        else:
            # Not admin subdomain
            request.is_admin_subdomain = False
            request.skip_tenant_check = False

            # No need to block /manager/ as it's now at root on admin subdomain only

        # Continue to next middleware (TenantMainMiddleware)
        return None
