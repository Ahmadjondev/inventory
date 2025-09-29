from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model

from accounts.serializers import UserSerializer
from .permissions import RolePermission
from drf_spectacular.utils import extend_schema

User = get_user_model()


@extend_schema(tags=["users"])
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, RolePermission]
    allowed_roles = [User.Roles.ADMIN]

    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def me(self, request):
        return Response(self.get_serializer(request.user).data)
