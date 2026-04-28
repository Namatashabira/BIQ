from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer_reviews', '0002_customerreview_reviewer_name'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerreview',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='customer_reviews',
                to='tenants.tenant',
            ),
        ),
    ]
