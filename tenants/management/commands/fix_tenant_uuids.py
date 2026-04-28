from django.core.management.base import BaseCommand
from tenants.models import Tenant
import uuid

class Command(BaseCommand):
    help = 'Fix duplicate or null UUIDs in Tenant table.'

    def handle(self, *args, **options):
        seen = set()
        updated = 0
        for tenant in Tenant.objects.all():
            if not tenant.uuid or tenant.uuid in seen:
                new_uuid = uuid.uuid4()
                while new_uuid in seen:
                    new_uuid = uuid.uuid4()
                tenant.uuid = new_uuid
                tenant.save(update_fields=['uuid'])
                updated += 1
            seen.add(tenant.uuid)
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} tenants with unique UUIDs.'))
