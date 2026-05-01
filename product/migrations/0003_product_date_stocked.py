from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0002_cloudinary_image_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='date_stocked',
            field=models.DateField(blank=True, null=True),
        ),
    ]
