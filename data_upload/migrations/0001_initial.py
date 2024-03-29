# Generated by Django 5.0.2 on 2024-02-23 19:49

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudyData',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('study_name', models.CharField(max_length=255)),
                ('sponsor_name', models.CharField(max_length=255)),
                ('created_date_time', models.DateTimeField(auto_now_add=True)),
                ('last_modified_date_time', models.DateTimeField(auto_now=True)),
                ('alias', models.CharField(blank=True, max_length=255, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='studies', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Study Data',
                'verbose_name_plural': 'Studies Data',
                'db_table': 'study_data',
            },
        ),
        migrations.CreateModel(
            name='ZipUploadData',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('original_file_name', models.CharField(max_length=255)),
                ('upload_date_time', models.DateTimeField(auto_now_add=True)),
                ('status', models.IntegerField(choices=[(1, 'SUCCESS'), (2, 'FAILURE'), (3, 'UPLOADED'), (4, 'UNZIP_COMPLETED'), (5, 'DOWNLOADED'), (6, 'PROCESSING')], default=None)),
                ('additional_info', models.TextField(blank=True, null=True)),
                ('version_number', models.IntegerField(default=-1)),
                ('date_lake_url', models.URLField(blank=True, max_length=255, null=True)),
                ('alias', models.CharField(blank=True, max_length=255, null=True)),
                ('study', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='file_uploads', to='data_upload.studydata')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zip_uploads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ZIP Upload Data',
                'verbose_name_plural': 'ZIP Upload Data',
                'db_table': 'zip_upload_data',
            },
        ),
        migrations.CreateModel(
            name='SheetUploadData',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('original_file_name', models.CharField(max_length=255)),
                ('upload_date_time', models.DateTimeField(auto_now_add=True)),
                ('status', models.IntegerField(choices=[(1, 'SUCCESS'), (2, 'FAILURE'), (3, 'UPLOADED'), (4, 'UNZIP_COMPLETED'), (5, 'DOWNLOADED'), (6, 'PROCESSING')], default=None)),
                ('additional_info', models.TextField(blank=True, null=True)),
                ('version_number', models.IntegerField(default=-1)),
                ('date_lake_url', models.URLField(blank=True, max_length=255, null=True)),
                ('alias', models.CharField(blank=True, max_length=255, null=True)),
                ('unique_reference', models.CharField(blank=True, max_length=255, null=True)),
                ('file_type', models.CharField(blank=True, max_length=255, null=True)),
                ('active', models.BooleanField(default=True)),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sheet_uploads', to=settings.AUTH_USER_MODEL)),
                ('study', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sheet_uploads', to='data_upload.studydata')),
                ('zip_upload', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sheet_uploads', to='data_upload.zipuploaddata')),
            ],
            options={
                'verbose_name': 'Sheet Upload Data',
                'verbose_name_plural': 'Sheet Upload Data',
                'db_table': 'sheet_upload_data',
            },
        ),
    ]
