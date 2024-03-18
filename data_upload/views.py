import sys
import uuid
from os import path

from azure.storage.blob import BlobServiceClient
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from .models import ZipUploadData, SheetUploadData, MongoDbClient
from .serializers import FileUploadDataSerializer, CsvUploadDataSerializer, CsvMetaData, CsvDataSerializer
from .tasks import download_file, process_zip_file, process_csv_file
from celery import chain


class FileUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        if 'file' not in request.FILES:
            print(request.FILES.keys())
            return Response({"message": "No file found in the request"}, status=400)
        file_obj = request.FILES['file']
        file_id = request.data.get('file_id')
        mongo_db_ref = request.data.get('mongo_db_ref')
        original_file_name = file_obj.name
        if mongo_db_ref and original_file_name.endswith('.zip'):
            return Response(
                {"message": "Invalid file type for versioning a file. Only CSV and XLSX files are supported."},
                status=400)
        # user = request.user  # Assuming you have user authentication in place

        # Generate a unique file name for storage
        blob_name = f"{uuid.uuid4()}_{original_file_name}"

        # Upload file to Azure Storage
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=settings.AZURE_STORAGE_CONTAINER_NAME,
                                                          blob=blob_name)
        blob_client.upload_blob(file_obj)

        # Generate URL for the uploaded file
        date_lake_url = blob_client.blob_name
        version_number = ZipUploadData.objects.get(id=file_id).version_number + 1 if file_id else 1

        # Save file upload details to the database
        if not mongo_db_ref:
            file_upload_data = ZipUploadData.objects.create(
                # user_id=user,
                study_id="5d6f921c-6296-44ea-a092-329c7d701751",
                original_file_name=original_file_name,
                date_lake_url=date_lake_url,
                status=1,  # Set initial status; adjust based on your logic
                version_number=version_number  # Set initial version; adjust based on your logic
            )

        if original_file_name.endswith('.zip'):
            chain(download_file.s(file_upload_data.id, None).set(queue='tasks'),
                  process_zip_file.s(file_upload_data.id).set(queue='tasks'),
                  process_csv_file.s(file_upload_data.id, None).set(queue='tasks')).apply_async()
            # download_file.apply_async(args=[file_upload_data.id])
        elif original_file_name.endswith('.csv') or original_file_name.endswith('.xlsx'):
            csv_version_number = SheetUploadData.objects.get(
                mongo_db_ref=mongo_db_ref).version_number + 1 if mongo_db_ref else 1
            ref = uuid.uuid4()
            csv_file_data = SheetUploadData.objects.create(
                file_upload=file_upload_data,
                original_file_name=original_file_name,
                mongo_db_ref=ref,
                comments="",
                alias="",
                version_number=csv_version_number,
                status="Uploaded"
            )
            chain(download_file.s(file_upload_data.id, ref).set(queue='tasks'),
                  process_csv_file.s(file_upload_data.id).set(queue='tasks')).apply_async()
        else:
            file_upload_data.status = "Invalid File Type"
            file_upload_data.save()
            return Response({"message": "Invalid file type. Only ZIP, CSV, and XLSX files are supported."}, status=400)

        serializer = FileUploadDataSerializer(file_upload_data)
        return Response(serializer.data)

    def get(self, request, *args, **kwargs):
        file_upload_id = request.query_params.get('file_upload_id')
        if not file_upload_id:
            return Response({"message": "file_upload_id is required"}, status=400)
        file_upload_data = ZipUploadData.objects.get(id=file_upload_id)
        serializer = FileUploadDataSerializer(file_upload_data)
        return Response(serializer.data)


class DataStagingView(APIView):

    def get(self, request, *args, **kwargs):
        file_upload_id = request.query_params.get('file_upload_id')
        if not file_upload_id:
            return Response({"message": "file_upload_id is required"}, status=400)
        file_upload_data = ZipUploadData.objects.get(id=file_upload_id)
        serializer = FileUploadDataSerializer(file_upload_data)
        if file_upload_data.status == "uploaded" or file_upload_data.status == "downloaded":
            return Response(serializer.data)

        csv_data_list = SheetUploadData.objects.filter(file_upload_id=file_upload_id)
        if not csv_data_list:
            return Response(serializer.data)
        csv_serializer = CsvUploadDataSerializer(csv_data_list, many=True)
        response_data = {
            "status": "SUCCESS",
            "file_upload_data": serializer.data,
            "csv_data": csv_serializer.data
        }
        return Response(response_data)


class AllAvailableDataSources(APIView):

    def get(self, request, *args, **kwargs):

        file_upload_data_list = ZipUploadData.objects.filter(status="processed")
        serializer = FileUploadDataSerializer(file_upload_data_list, many=True)
        return Response(serializer.data)


class CsvMetaDataView(APIView):

    def get(self, request, *args, **kwargs):
        file_upload_id = request.query_params.get('file_upload_id')
        mongo_db_ref = request.query_params.get('mongo_db_ref')
        if mongo_db_ref:
            csv_meta_data = MongoDbClient.objects.only("_id", "sql_ref", "column_data").get(sql_ref=mongo_db_ref)
            if not csv_meta_data:
                return Response({"message": "No mongo db client found for the reference"}, status=400)
            serializer = CsvMetaData(csv_meta_data)
            return Response(serializer.data)

        if not file_upload_id:
            return Response({"message": "file_upload_id is required"}, status=400)
        file_upload_data = ZipUploadData.objects.get(id=file_upload_id)
        if not file_upload_data:
            return Response({"message": "No file upload data found for the file upload id"}, status=400)
        if not file_upload_data.status == "processed":
            return Response({"message": "File processing in progress"}, status=400)

        csv_data_list = SheetUploadData.objects.filter(file_upload_id=file_upload_id)
        if not csv_data_list:
            return Response({"message": "No CSV data found for the file upload id"}, status=400)

        csv_meta_data_list = []
        for csv_data in csv_data_list:
            mongo_db_ref = csv_data.unique_reference
            if mongo_db_ref:
                csv_meta_data = MongoDbClient.objects.only("_id", "sql_ref", "column_data").get(sql_ref=mongo_db_ref)
                if csv_meta_data:
                    csv_meta_data_list.append(csv_meta_data)

        serializer = CsvMetaData(csv_meta_data_list, many=True)
        return Response(serializer.data)


class FetchDataFromCSV(APIView):

    def get(self, request, *args, **kwargs):
        mongo_db_ref = request.query_params.get('mongo_db_ref')
        if not mongo_db_ref:
            return Response({"message": "mongo_db_ref is required"}, status=400)

        csv_meta_data = MongoDbClient.objects.only("_id", "data").get(sql_ref=mongo_db_ref)
        if not csv_meta_data:
            return Response({"message": "No mongo db client found for the reference"}, status=400)

        serializer = CsvDataSerializer(csv_meta_data)
        return Response(serializer.data)
