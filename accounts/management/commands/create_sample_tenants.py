# accounts/management/commands/create_sample_tenants.py
from django.core.management.base import BaseCommand
from accounts.models import Client, Domain

class Command(BaseCommand):
    help = "Create multiple sample tenants with domains"

    def handle(self, *args, **options):
        tenants = [
            {"schema_name": "tenant1", "name": "Filial 1", "domain": "tenant1.localhost"},
            {"schema_name": "tenant2", "name": "Filial 2", "domain": "tenant2.localhost"},
            {"schema_name": "tenant3", "name": "Filial 3", "domain": "tenant3.localhost"},
        ]

        for t in tenants:
            tenant, created = Client.objects.get_or_create(
                schema_name=t["schema_name"],
                defaults={
                    "name": t["name"],
                    "paid_until": "2025-12-31",
                    "on_trial": True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Tenant '{t['name']}' created."))

            domain, dom_created = Domain.objects.get_or_create(
                domain=t["domain"],
                tenant=tenant,
                defaults={"is_primary": True}
            )
            if dom_created:
                self.stdout.write(self.style.SUCCESS(f"Domain '{t['domain']}' created."))
