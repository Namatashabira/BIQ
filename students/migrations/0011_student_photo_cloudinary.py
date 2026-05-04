from django.db import migrations
try:
    from cloudinary.models import CloudinaryField
    _cloudinary_available = True
except ImportError:
    import django.db.models as models
    _cloudinary_available = False


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0010_generatedreport'),
    ]

    operations = [
        migrations.AlterField(
            model_name='student',
            name='photo',
            field=CloudinaryField('photo', folder='student_photos', blank=True, null=True)
            if _cloudinary_available
            else __import__('django.db.models', fromlist=['ImageField']).ImageField(
                upload_to='student_photos/', blank=True, null=True
            ),
        ),
    ]
