import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_order_tenant_fk'),
        ('tenants', '0007_uuid_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='receipt',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='receipts',
                to='tenants.tenant',
                db_index=True,
            ),
        ),
    ]
