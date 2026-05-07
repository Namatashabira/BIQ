import hmac
import hashlib
import secrets
from datetime import date
from django.db import migrations, models


def backfill_receipt_numbers(apps, schema_editor):
    FeePayment = apps.get_model('fees', 'FeePayment')
    from django.conf import settings
    secret = (settings.SECRET_KEY or 'fallback').encode()
    seen = set()
    for payment in FeePayment.objects.all():
        for _ in range(10):
            rand = secrets.token_hex(4).upper()
            date_part = (payment.payment_date or date.today()).strftime('%Y%m%d')
            payload = f"{date_part}-{rand}"
            check = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:6].upper()
            candidate = f"RCP-{date_part}-{rand}-{check}"
            if candidate not in seen:
                seen.add(candidate)
                payment.receipt_number = candidate
                payment.save(update_fields=['receipt_number'])
                break


class Migration(migrations.Migration):

    dependencies = [
        ('fees', '0006_fee_items'),
    ]

    operations = [
        # 1. Add without unique so existing rows can get empty string
        migrations.AddField(
            model_name='feepayment',
            name='receipt_number',
            field=models.CharField(blank=True, max_length=40, default=''),
            preserve_default=False,
        ),
        # 2. Backfill unique values for existing rows
        migrations.RunPython(backfill_receipt_numbers, migrations.RunPython.noop),
        # 3. Now add the unique + index constraint
        migrations.AlterField(
            model_name='feepayment',
            name='receipt_number',
            field=models.CharField(blank=True, db_index=True, max_length=40, unique=True),
        ),
    ]
