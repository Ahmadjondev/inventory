"""
Custom JWT views with tenant validation
"""

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db import connection
from django_tenants.utils import get_public_schema_name


class TenantAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom serializer that validates tenant membership before issuing JWT tokens.
    """

    def validate(self, attrs):
        """
        Validate credentials and tenant membership.
        """
        # Use our custom authentication backend
        user = authenticate(
            request=self.context.get("request"),
            username=attrs.get(self.username_field),
            password=attrs.get("password"),
        )

        if user is None:
            # Get current schema for better error message
            current_schema = connection.schema_name
            public_schema = get_public_schema_name()
            print(f"Authentication failed on schema: {current_schema}")
            print(f"User attempted: {attrs.get(self.username_field)}")
            print(f"Public schema: {public_schema}")

            if current_schema != public_schema:
                # Accessing a tenant schema - might be wrong tenant
                raise serializers.ValidationError(
                    "Unable to log in with provided credentials for this tenant.",
                    code="tenant_auth_failed",
                )
            else:
                raise serializers.ValidationError(
                    "Unable to log in with provided credentials.", code="authorization"
                )

        if not user.is_active:
            raise serializers.ValidationError(
                "User account is disabled.", code="user_inactive"
            )

        # Generate tokens
        refresh = self.get_token(user)

        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        return data


class TenantAwareTokenObtainPairView(TokenObtainPairView):
    """
    Custom token view that uses tenant-aware authentication.
    """

    serializer_class = TenantAwareTokenObtainPairSerializer
