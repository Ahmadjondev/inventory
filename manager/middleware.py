from django.utils.deprecation import MiddlewareMixin
from django.http import Http404
from django.conf import settings
from django.shortcuts import redirect


class AdminSubdomainMiddleware(MiddlewareMixin):
    def process_request(self, request):
        host = request.get_host().split(":")[0]
        subdomain = host.split(".")[0].lower()
        path = request.path_info

        # Allow static/media
        if path.startswith(settings.STATIC_URL) or path.startswith(
            getattr(settings, "MEDIA_URL", "/media/")
        ):
            request.skip_tenant_check = True
            return None

        # Admin subdomain
        if subdomain == "admin":
            request.is_admin_subdomain = True
            request.skip_tenant_check = True
            return None

        # Tenant subdomain
        request.is_admin_subdomain = False
        request.skip_tenant_check = False

        return None
