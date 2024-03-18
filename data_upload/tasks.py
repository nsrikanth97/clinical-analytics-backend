import json
import os
import csv
import shutil
import uuid
import zipfile
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from celery import shared_task
from .models import ZipUploadData, SheetUploadData, MongoDbClient, DataImportStatusEnum, SheetMetaData
from django.conf import settings
import logging
import openpyxl

logger = logging.getLogger(__name__)


@shared_task
def download_file(zip_upload_id, sheet_id, queue='tasks'):
    if not sheet_id and not zip_upload_id:
        logger.error("File upload id or sheet id not found in the request")
        return
    if zip_upload_id:
        logger.info("Downloading zip file with id {}".format(zip_upload_id))
        upload_data = ZipUploadData.objects.get(id=zip_upload_id)
    else:
        logger.info("Downloading sheet file with id {}".format(sheet_id))
        upload_data = SheetUploadData.objects.get(id=sheet_id)

    logger.info("Downloading file {}".format(upload_data.original_file_name))
    upload_data.status = DataImportStatusEnum.DOWNLOADED

    download_path = settings.TEMP_FILE_PATH + "/" + str(upload_data.study_id)
    if not os.path.exists(download_path):
        os.makedirs(download_path)
        logger.info("Directory created for file download at {}".format(download_path))
    if sheet_id:
        download_path = os.path.join(download_path, "extracted_files")
        if not os.path.exists(download_path):
            os.makedirs(download_path)
        logger.info("Directory created for file download at {}".format(download_path))
        extension = os.path.splitext(upload_data.original_file_name)[1]
        upload_data.file_type = extension
        logger.info("Extension of the file is {}".format(extension))
        sheet_ref = str(upload_data.id) + extension
        download_path = os.path.join(download_path, sheet_ref)
        logger.info("Download path for the file is {}".format(download_path))
    else:
        download_path = os.path.join(download_path, upload_data.original_file_name)
        logger.info("Download path for the zip file is {}".format(download_path))

    try:
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=settings.AZURE_STORAGE_CONTAINER_NAME,
                                                          blob=upload_data.date_lake_url)
        with open(download_path, "wb") as my_blob:
            logger.info("Downloading file from Azure Storage")
            download_stream = blob_client.download_blob()
            my_blob.write(download_stream.readall())
        logger.info("File downloaded successfully")
        upload_data.save()
    except Exception as e:
        logger.error("Error while downloading file from Azure Storage: {}".format(e))
        upload_data.status = DataImportStatusEnum.FAILURE
        upload_data.save()
        return
    logger.info("File download completed successfully for file {}".format(upload_data.original_file_name))
    return zip_upload_id if zip_upload_id else sheet_id


@shared_task
def process_zip_file(zip_upload_id, queue='tasks'):
    if not zip_upload_id:
        logger.error("File upload id not found in the request")
        return
    logger.info("Processing zip file with id {}".format(zip_upload_id))
    zip_upload_data = ZipUploadData.objects.get(id=zip_upload_id)
    if not zip_upload_data:
        logger.error("Invalid file id for processing a zip file")
        return

    zip_upload_data.status = DataImportStatusEnum.UNZIP_COMPLETED
    zip_dir_path = os.path.join(settings.TEMP_FILE_PATH, str(zip_upload_data.study_id))
    zip_file_path = os.path.join(zip_dir_path, zip_upload_data.original_file_name)
    sheet_dir_path = os.path.join(zip_dir_path, "extracted_files")
    if not os.path.exists(sheet_dir_path):
        os.makedirs(sheet_dir_path)
        logger.info("Directory created for extracted files at {}".format(sheet_dir_path))

    with zipfile.ZipFile(str(zip_file_path), 'r') as zip_ref:
        for file_name in zip_ref.namelist():
            if file_name.endswith('.csv') or file_name.endswith('.xlsx'):
                file_extension = os.path.splitext(file_name)[1]
                unique_ref = str(uuid.uuid4())
                existing_file = SheetUploadData.objects.filter(original_file_name=file_name,
                                                               study_id=zip_upload_data.study_id, active=True)
                version_number = 1
                if existing_file:
                    version_number = existing_file.latest('version_number').version_number + 1
                sheet_upload_data = SheetUploadData.objects.create(
                    zip_upload_id=zip_upload_id,
                    original_file_name=file_name,
                    unique_reference=unique_ref,
                    version_number=version_number,
                    uploaded_by=zip_upload_data.uploaded_by,
                    status=DataImportStatusEnum.UPLOADED,
                    file_type=file_extension,
                    study_id=zip_upload_data.study_id,
                    active=False
                )
                logger.info("Sheet file {} created with unique reference {}".format(file_name, unique_ref))
                new_file_path = os.path.join(sheet_dir_path, str(sheet_upload_data.id) + file_extension)
                source = zip_ref.open(file_name)
                target = open(new_file_path, "wb")
                logger.info("Extracting file {} to {}".format(file_name, new_file_path))
                try:
                    with source, target:
                        target.write(source.read())
                except Exception as e:
                    logger.error("Error while extracting file: {}".format(e))
                    sheet_upload_data.status = DataImportStatusEnum.FAILURE
                    sheet_upload_data.save()
                    continue
    zip_upload_data.save()
    return zip_upload_id


@shared_task
def wrapper_process_csv_file(sheet_id):
    return process_csv_file(None, sheet_id)


@shared_task
def process_csv_file(zip_upload_id, sheet_id, queue='tasks'):
    logger.info("Processing csv file with zip id {} and sheet id {}".format(zip_upload_id, sheet_id))
    if not zip_upload_id and not sheet_id:
        logger.error("File upload id or sheet id not found in the request")
        return
    sheet_data_list = []
    if zip_upload_id:
        logger.info("Processing all the sheets in the zip file with id {}".format(zip_upload_id))
        upload_data = ZipUploadData.objects.get(id=zip_upload_id)
        sheet_upload_data_list = SheetUploadData.objects.filter(zip_upload=zip_upload_id)
        sheet_data_list.extend(sheet_upload_data_list)
        logger.info("Total number of sheets to be processed: {}".format(len(sheet_data_list)))
    else:
        logger.info("Processing sheet file with id {}".format(sheet_id))
        upload_data = SheetUploadData.objects.get(id=sheet_id)
        sheet_data_list.append(upload_data)

    if len(sheet_data_list) <= 0:
        logger.error("No sheet data found for processing")
        return
    main_dir_path = os.path.join(settings.TEMP_FILE_PATH, str(upload_data.study_id))
    sheet_dir_path = os.path.join(main_dir_path, "extracted_files")
    chunk_size = settings.ITER_CHUNK_SIZE
    for sheet_data in sheet_data_list:
        csv_file_path = os.path.join(sheet_dir_path, str(sheet_data.id) + sheet_data.file_type)
        logger.info("Processing sheet file {} with id {}".format(sheet_data.original_file_name, sheet_data.id))
        if os.path.exists(csv_file_path):
            data = []
            column_data = []
            alphabet = 'B'
            if sheet_data.file_type == ".csv":
                with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
                    csv_reader = csv.DictReader(csvfile)
                    data = [row for row in csv_reader]

                    for index, column in enumerate(csv_reader.fieldnames):
                        sample_data = data[0][column] if data else ""
                        data_type = infer_data_type(sample_data)
                        column_data.append(
                            {"name": column, "data_type": data_type, "column_index": index + 1, "alphabet": alphabet})
                        alphabet = chr(ord(alphabet) + 1)
            elif sheet_data.file_type == ".xlsx":
                wb = openpyxl.load_workbook(csv_file_path)
                sheet = wb.active
                columns = []
                for i, row in enumerate(sheet.iter_rows(values_only=True)):
                    if i == 0:
                        columns = row
                        column_data = [{"name": column, "column_index": index + 1, "alphabet": alphabet} for
                                       index, column in
                                       enumerate(columns)]
                        alphabet = chr(ord(alphabet) + 1)
                    else:
                        row_data = {columns[j]: value for j, value in enumerate(row)}
                        data.append(row_data)
                for column in column_data:
                    sample_data = data[0][column["name"]] if data else ""
                    data_type = infer_data_type(sample_data)
                    column["data_type"] = data_type
            else:
                logger.error("Invalid file type for processing: {}".format(sheet_data.file_type))
                sheet_data.status = DataImportStatusEnum.FAILURE
                sheet_data.save()
                continue
            column_data.append(
                {"name": "sct_id", "data_type": "string", "column_index": 0, "visible": False, "alphabet": 'A'})
            sheet_metadata = SheetMetaData.objects.create(
                sql_ref=str(sheet_data.unique_reference),
                column_data=column_data
            )
            data_chunk = []
            logger.info("Processing data in chunks of size {}".format(chunk_size))
            index = 0
            for row in data:
                row["sct_id"] = "SCT" + str(uuid.uuid4())

                data_chunk.append(row)
                index += 1

                if index % chunk_size == 0:
                    logger.info(row)
                    MongoDbClient.objects.create(
                        sql_ref=str(sheet_data.unique_reference),
                        meta_data=sheet_metadata,
                        data=data_chunk
                    )
                    data_chunk = []

            if len(data_chunk) > 0:
                MongoDbClient.objects.create(
                    sql_ref=str(sheet_data.unique_reference),
                    meta_data=sheet_metadata,
                    data=data_chunk
                )

            sheet_data.status = DataImportStatusEnum.SUCCESS
            existing_file = SheetUploadData.objects.filter(original_file_name=sheet_data.original_file_name,
                                                           study_id=sheet_data.study_id, active=True)
            existing_file.update(active=False)
            sheet_data.active = True
            sheet_data.save()
        else:
            logger.error("File not found at the path: {}".format(csv_file_path))
            sheet_data.status = DataImportStatusEnum.FAILURE
            sheet_data.save()
    if zip_upload_id:
        upload_data.status = DataImportStatusEnum.SUCCESS
        upload_data.save()
    shutil.rmtree(main_dir_path)
    logger.info("File processing completed successfully for file {}".format(upload_data.original_file_name))


def infer_data_type(value):
    # Try to convert to an integer
    try:
        try:
            int(value)
            return "integer"
        except ValueError:
            pass

        # Try to convert to a float
        try:
            float(value)
            return "float"
        except ValueError:
            pass

        value_lower = value.lower()
        if value_lower == "true" or value_lower == "false":
            return "boolean"

        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%m-%d-%Y', '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y', ''):
            try:
                datetime.strptime(value, fmt)
                return "date"
            except ValueError:
                pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %I:%M %p'):
            try:
                datetime.strptime(value, fmt)
                return "datetime"
            except ValueError:
                pass

        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                datetime.strptime(value, fmt)
                return "time"
            except ValueError:
                pass
        for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%d/%m/%Y %H:%M:%S %Z", "%m/%d/%Y %H:%M:%S %Z"):
            try:
                datetime.strptime(value, fmt)
                return "datetime"
            except ValueError:
                pass
    except Exception as e:
        logger.error("Error while inferring data type: {}".format(e))
        return "string"
    return "string"
