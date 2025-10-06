"""
Custom error handlers for the API.
"""

from django.http import JsonResponse


def handler404(request, exception=None):
    """
    Custom 404 handler that returns JSON for API requests.
    """
    # Check if this is likely a tenant not found error
    error_msg = str(exception) if exception else ""
    if "no tenant for hostname" in error_msg.lower():
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

    # Default 404 response
    return JsonResponse(
        {
            "error": "Not Found",
            "message": "The requested resource was not found.",
            "path": request.path,
        },
        status=404,
    )


def handler500(request):
    """
    Custom 500 handler that returns JSON for API requests.
    """
    return JsonResponse(
        {
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
        },
        status=500,
    )
