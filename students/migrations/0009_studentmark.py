from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0008_student_fees_balance_student_payment_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentMark',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=100)),
                ('competency', models.CharField(blank=True, max_length=200)),
                ('term', models.CharField(max_length=20)),
                ('academic_year', models.CharField(max_length=20)),
                ('ca_score', models.FloatField(blank=True, null=True)),
                ('exam_score', models.FloatField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='marks', to='students.student')),
            ],
            options={
                'ordering': ['subject'],
                'unique_together': {('student', 'subject', 'term', 'academic_year')},
            },
        ),
    ]
