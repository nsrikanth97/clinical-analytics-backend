# Generated by Django 5.0.2 on 2024-03-06 15:02

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_upload', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomColumnData',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('column_name', models.CharField(max_length=255)),
                ('data_type', models.CharField(max_length=50)),
                ('created_date_time', models.DateTimeField(auto_now_add=True)),
                ('input_type', models.DateTimeField(auto_now=True)),
                ('formula_string', models.CharField(blank=True, max_length=255, null=True)),
                ('sheet_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_column_data', to='data_upload.sheetuploaddata')),
            ],
            options={
                'verbose_name': 'Custom Column Data',
                'verbose_name_plural': 'Custom Column Data',
                'db_table': 'custom_column_data',
            },
        ),
    ]