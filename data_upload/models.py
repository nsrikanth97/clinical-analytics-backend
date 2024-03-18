import uuid
from enum import IntEnum

from django.db import models
# from djongo import models as djongo_models
from mongoengine import Document, StringField, DictField, ListField, EmbeddedDocumentListField, \
    EmbeddedDocument, ReferenceField, BooleanField, IntField


class DataImportStatusEnum(IntEnum):
    SUCCESS = 1
    FAILURE = 2
    UPLOADED = 3
    UNZIP_COMPLETED = 4
    DOWNLOADED = 5
    PROCESSING = 6


class StudyData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    study_name = models.CharField(max_length=255, null=False, blank=False)
    user = models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='studies')
    sponsor_name = models.CharField(max_length=255, null=False, blank=False)
    created_date_time = models.DateTimeField(auto_now_add=True)
    last_modified_date_time = models.DateTimeField(auto_now=True)
    alias = models.CharField(max_length=255, null=True, blank=True)

    objects = models.Manager()

    class Config:
        arbitrary_types_allowed = True

    class Meta:
        db_table = 'study_data'
        verbose_name = 'Study Data'
        verbose_name_plural = 'Studies Data'


class UploadData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    original_file_name = models.CharField(max_length=255, null=False, blank=False)
    upload_date_time = models.DateTimeField(auto_now_add=True)
    status = models.IntegerField(
        choices=[(status.value, status.name) for status in DataImportStatusEnum],
        default=None
    )
    additional_info = models.TextField(blank=True, null=True)
    version_number = models.IntegerField(default=-1)
    uploaded_by = models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='sheet_uploads')
    date_lake_url = models.URLField(max_length=255, null=True, blank=True)
    alias = models.CharField(max_length=255, null=True, blank=True)

    objects = models.Manager()

    class Meta:
        abstract = True

    def __str__(self):
        return "{} ({})".format(self.original_file_name, self.status)


class ZipUploadData(UploadData):
    study = models.ForeignKey('StudyData', on_delete=models.CASCADE, related_name='file_uploads')
    uploaded_by = models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='zip_uploads')

    class Config:
        arbitrary_types_allowed = True

    class Meta:
        db_table = 'zip_upload_data'
        verbose_name = 'ZIP Upload Data'
        verbose_name_plural = 'ZIP Upload Data'

    def __str__(self):
        return "{} ({})".format(self.original_file_name, self.status)


class SheetUploadData(UploadData):
    zip_upload = models.ForeignKey('ZipUploadData', on_delete=models.CASCADE, related_name='sheet_uploads', null=True,
                                   blank=True)
    unique_reference = models.CharField(max_length=255, null=True, blank=True)
    file_type = models.CharField(max_length=255, null=True, blank=True)
    study = models.ForeignKey('StudyData', on_delete=models.CASCADE, related_name='sheet_uploads')
    active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sheet_upload_data'
        verbose_name = 'Sheet Upload Data'
        verbose_name_plural = 'Sheet Upload Data'

    def __str__(self):
        return self.original_file_name


class ColumnData(EmbeddedDocument):
    name = StringField(max_length=255)
    data_type = StringField(max_length=50)
    column_index = IntField()
    input_type = StringField(max_length=50, default="UPL")
    formula_string = StringField(max_length=255)
    format_string = StringField(max_length=255)
    resizable = BooleanField(default=True)
    visible = BooleanField(default=True)
    protected = BooleanField(default=True)
    alphabet = StringField(max_length=2)


class SheetMetaData(Document):
    sql_ref = StringField(max_length=255, null=False, blank=False)
    column_data = EmbeddedDocumentListField(ColumnData)

    meta = {
        'db_table': 'sheet_meta_data',
        'verbose_name': 'Sheet Meta Data',
        'mongodb_model': True,
        'verbose_name_plural': 'Sheet Meta Data'
    }

    def __str__(self):
        return self.sql_ref


class MongoDbClient(Document):
    # MongoEngine automatically creates an "_id" field with ObjectIdField type
    sql_ref = StringField(max_length=255, null=False, blank=False)
    data = ListField(DictField())  # List of embedded RowData
    meta_data = ReferenceField(SheetMetaData, required=True)

    meta = {
        'db_table': 'mongo_db_client',
        'verbose_name': 'MongoDB Client',
        'mongodb_model': True,
        'verbose_name_plural': 'MongoDB Clients'
    }

    def __str__(self):
        return "{} ({})".format(self.id, self.sql_ref)  # Using MongoEngine's "id"


class CustomColumnData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    sheet_id = models.ForeignKey('SheetUploadData', on_delete=models.CASCADE, related_name='custom_column_data')
    column_name = models.CharField(max_length=255, null=False, blank=False)
    column_index = models.IntegerField(null=True, blank=False)
    created_date_time = models.DateTimeField(auto_now_add=True)
    input_type = models.CharField(max_length=50, null=False, blank=False)
    formula_string = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'custom_column_data'
        verbose_name = 'Custom Column Data'
        verbose_name_plural = 'Custom Column Data'
