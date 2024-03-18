from rest_framework import serializers
from .models import ZipUploadData, SheetUploadData, ColumnData, MongoDbClient


class FileUploadDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZipUploadData
        fields = ['id', 'original_file_name', 'upload_date_time', 'status',
                  'additional_info', 'version_number']


class CsvUploadDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SheetUploadData
        fields = ['id', 'file_upload', 'original_file_name', 'upload_date_time', 'mongo_db_ref',
                  'comments', 'alias', 'version_number', 'file_type', 'status']


class ColumnDataSerializer(serializers.Serializer):
    column_name = serializers.CharField(max_length=255)
    data_type = serializers.CharField(max_length=50)

    class Meta:
        model = ColumnData
        fields = ['column_name', 'data_type']


class CsvMetaData(serializers.Serializer):
    _id = serializers.CharField(max_length=255)
    sql_ref = serializers.CharField(max_length=255)
    column_data = ColumnDataSerializer(many=True)

    class Meta:
        model = MongoDbClient
        fields = ['_id', 'sql_ref', 'column_data']


class CsvDataSerializer(serializers.Serializer):
    data = serializers.JSONField()
    _id = serializers.CharField(max_length=255)

    class Meta:
        model = MongoDbClient
        fields = ['data', '_id']
