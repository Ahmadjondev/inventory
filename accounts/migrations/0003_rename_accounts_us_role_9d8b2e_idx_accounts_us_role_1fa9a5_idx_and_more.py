"""Deprecated migration (index rename + field alter) rendered unnecessary after squash.

Kept as empty placeholder so historical references remain valid. Safe to delete on new setups.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = []
