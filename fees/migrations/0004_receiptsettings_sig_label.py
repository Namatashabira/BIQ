from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fees', '0003_receiptsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='receiptsettings',
            name='sig_label',
            field=models.CharField(blank=True, default='Bursar', max_length=100),
        ),
    ]
