"""
Management command to create default subscription plans.
"""

from django.core.management.base import BaseCommand
from accounts.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Creates default subscription plans (Basic, Pro, Enterprise)"

    def handle(self, *args, **options):
        plans_data = [
            {
                "name": "Basic Plan",
                "plan_type": SubscriptionPlan.PlanType.BASIC,
                "description": "Perfect for small businesses just getting started",
                "price_monthly": 29.99,
                "price_yearly": 299.99,
                "max_users": 3,
                "max_products": 500,
                "max_warehouses": 1,
                "max_branches": 1,
                "has_advanced_reporting": False,
                "has_api_access": False,
                "has_multi_currency": True,
                "has_customer_management": True,
                "has_offline_support": False,
            },
            {
                "name": "Pro Plan",
                "plan_type": SubscriptionPlan.PlanType.PRO,
                "description": "For growing businesses that need more features",
                "price_monthly": 79.99,
                "price_yearly": 799.99,
                "max_users": 10,
                "max_products": 5000,
                "max_warehouses": 3,
                "max_branches": 3,
                "has_advanced_reporting": True,
                "has_api_access": True,
                "has_multi_currency": True,
                "has_customer_management": True,
                "has_offline_support": True,
            },
            {
                "name": "Enterprise Plan",
                "plan_type": SubscriptionPlan.PlanType.ENTERPRISE,
                "description": "For large businesses with complex needs",
                "price_monthly": 199.99,
                "price_yearly": 1999.99,
                "max_users": 50,
                "max_products": 50000,
                "max_warehouses": 10,
                "max_branches": 10,
                "has_advanced_reporting": True,
                "has_api_access": True,
                "has_multi_currency": True,
                "has_customer_management": True,
                "has_offline_support": True,
            },
        ]

        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.get_or_create(
                plan_type=plan_data["plan_type"], defaults=plan_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully created plan: {plan.name}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Plan already exists: {plan.name}")
                )

        self.stdout.write(
            self.style.SUCCESS("Subscription plans initialization complete!")
        )
