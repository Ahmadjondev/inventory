"""
Tenant-aware authentication backend
"""

from django.contrib.auth.backends import ModelBackend
from django.db import connection
from django.contrib.auth import get_user_model
from django_tenants.utils import get_public_schema_name

User = get_user_model()


class TenantAwareAuthBackend(ModelBackend):
    """
    Custom authentication backend that enforces tenant membership.

    Rules:
    1. SuperAdmins (role=SUPERADMIN, tenant_schema='') can access any schema
    2. Regular users can ONLY access their assigned tenant schema
    3. Authentication fails if user tries to access wrong tenant
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user with tenant context awareness.
        """
        if username is None or password is None:
            return None

        try:
            # Get user from database
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user
            User().set_password(password)
            return None

        # Check password
        if not user.check_password(password):
            return None

        # Check if user is active
        if not self.user_can_authenticate(user):
            return None

        # Get current schema from connection
        current_schema = connection.schema_name
        public_schema = get_public_schema_name()

        # SuperAdmins can access any schema
        if user.role == User.Roles.SUPERADMIN and not user.tenant_schema:
            return user

        # For tenant schemas: verify user belongs to this tenant
        if current_schema != public_schema:
            if user.tenant_schema != current_schema:
                # User trying to access wrong tenant
                return None

        # For public schema: only allow SuperAdmins
        if current_schema == public_schema:
            if user.role != User.Roles.SUPERADMIN:
                return None

        return user
