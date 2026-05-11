from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0008_add_worker_school_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='school_type',
            field=models.CharField(
                blank=True,
                choices=[('primary', 'Primary School'), ('secondary', 'Secondary School')],
                default='',
                help_text='Only applicable when business_type is school',
                max_length=20,
            ),
        ),
    ]
