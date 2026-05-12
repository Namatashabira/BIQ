import uuid
from django.db import migrations, models


def populate_tokens(apps, schema_editor):
    GeneratedReport = apps.get_model('students', 'GeneratedReport')
    for report in GeneratedReport.objects.all():
        report.secure_token = uuid.uuid4()
        report.save(update_fields=['secure_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0014_student_school_type_alter_stream_class_label_and_more'),
    ]

    operations = [
        # Step 1: add nullable (no unique yet — avoids the collision)
        migrations.AddField(
            model_name='generatedreport',
            name='secure_token',
            field=models.UUIDField(null=True, blank=True, db_index=True),
        ),
        # Step 2: fill every existing row with a unique UUID
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
        # Step 3: make it non-nullable and unique
        migrations.AlterField(
            model_name='generatedreport',
            name='secure_token',
            field=models.UUIDField(default=uuid.uuid4, unique=True, db_index=True),
        ),
    ]
