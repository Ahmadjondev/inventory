"""Accounts app exposes multi-tenant Client/Domain models and custom User with role-based access.

RolePermission (in views.py) can be reused by other apps importing as:
	from accounts.views import RolePermission, User
"""

