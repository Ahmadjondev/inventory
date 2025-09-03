from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from inventory.models import Product, Order


@receiver(post_migrate)
def create_roles(sender, **kwargs):
    roles = {
        "Admin": [
            "add_product",
            "change_product",
            "delete_product",
            "view_product",
            "add_order",
            "change_order",
            "delete_order",
            "view_order",
        ],
        "Kassir": ["add_order", "change_order", "view_order"],
        "Omborchi": ["add_product", "change_product", "delete_product", "view_product"],
        "Buxgalter": ["view_order", "view_product"],
    }

    for role_name, perms in roles.items():
        group, created = Group.objects.get_or_create(name=role_name)
        for perm_codename in perms:
            try:
                app_label, model_name, action = perm_codename.split("_")
            except ValueError:
                pass

        for codename in perms:
            try:
                perm = Permission.objects.get(codename=codename)
                group.permissions.add(perm)
            except Permission.DoesNotExist:
                pass
