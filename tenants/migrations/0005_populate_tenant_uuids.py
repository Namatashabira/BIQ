from django.db import migrations
import uuid

def populate_tenant_uuids(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    for tenant in Tenant.objects.filter(uuid__isnull=True):
        tenant.uuid = uuid.uuid4()
        tenant.save(update_fields=['uuid'])

class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0004_alter_tenant_uuid'),
    ]
    operations = [
        migrations.RunPython(populate_tenant_uuids, reverse_code=migrations.RunPython.noop),
    ]
