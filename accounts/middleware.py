"""
Custom middleware for enhanced tenant handling.
"""

from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django_tenants.utils import get_tenant_domain_model
from django.core.exceptions import DisallowedHost


class StrictTenantMiddleware:
    """
    Middleware to enforce strict domain checking and provide helpful error messages.
    Should be placed after CustomTenantMiddleware (or TenantMainMiddleware).

    This middleware catches exceptions from tenant resolution and returns
    user-friendly JSON error responses instead of HTML error pages.

    Skips checks for admin subdomain requests (marked by AdminSubdomainMiddleware).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Process the request and handle tenant-related errors.
        """
        # Skip tenant checks for admin subdomain
        if getattr(request, "skip_tenant_check", False):
            return self.get_response(request)
        path = request.path_info
        if not path.startswith("/api/"):
            # Tenant should not access non-API routes
            return redirect("/api/docs/")
            raise Http404("Only /api/ endpoints are allowed for tenant subdomains.")

        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Handle tenant not found errors
            error_msg = str(e).lower()
            if "no tenant for hostname" in error_msg or "no tenant found" in error_msg:
                hostname = request.get_host().split(":")[0]
                return JsonResponse(
                    {
                        "error": "Tenant Not Found",
                        "message": f"No tenant exists for domain '{hostname}'. Please check the URL or contact your administrator.",
                        "domain": hostname,
                        "hint": "Make sure you're using the correct subdomain (e.g., demo.localhost:8001)",
                    },
                    status=404,
                )
            # Re-raise other exceptions
            raise

    def process_exception(self, request, exception):
        """
        Handle exceptions raised during request processing.
        This catches exceptions from tenant middleware.
        """
        # Skip for admin subdomain
        if getattr(request, "skip_tenant_check", False):
            return None
        error_msg = str(exception).lower()

        # Handle tenant not found
        if "no tenant for hostname" in error_msg or "no tenant found" in error_msg:
            hostname = request.get_host().split(":")[0]
            return JsonResponse(
                {
                    "error": "Tenant Not Found",
                    "message": f"No tenant exists for domain '{hostname}'. Please check the URL or contact your administrator.",
                    "domain": hostname,
                    "hint": "Make sure you're using the correct subdomain (e.g., demo.localhost:8001)",
                },
                status=404,
            )

        # Check tenant status (if we got this far, tenant exists but may be inactive)
        hostname = request.get_host().split(":")[0]
        DomainModel = get_tenant_domain_model()
        try:
            domain = DomainModel.objects.select_related("tenant").get(domain=hostname)

            if hasattr(domain.tenant, "status"):
                if domain.tenant.status == "suspended":
                    return JsonResponse(
                        {
                            "error": "Tenant Suspended",
                            "message": f"This tenant ({domain.tenant.name}) has been suspended. Please contact support.",
                            "domain": hostname,
                        },
                        status=403,
                    )
                elif domain.tenant.status == "expired":
                    return JsonResponse(
                        {
                            "error": "Subscription Expired",
                            "message": f"The subscription for this tenant ({domain.tenant.name}) has expired. Please renew to continue.",
                            "domain": hostname,
                        },
                        status=403,
                    )
        except DomainModel.DoesNotExist:
            pass  # Already handled above

        return None
