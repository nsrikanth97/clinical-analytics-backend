import uuid

import jwt
import pymongo
from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient
from celery import chain
from django.conf import settings
from ninja import NinjaAPI, UploadedFile, File, Form
from .tasks import download_file, process_zip_file, process_csv_file, wrapper_process_csv_file
from .models import ZipUploadData, SheetUploadData, DataImportStatusEnum, StudyData, SheetMetaData, MongoDbClient, \
    CustomColumnData, ColumnData
from .schemas import ZipUploadResponseObject, SheetUploadResponseObject, StudyDataResponseObject, \
    StudyListResponseObject, SingleStudyResponseObject, SingleStudyDataSchema, StudyDataSchema, ZipUploadDataSchema, \
    SheetUploadDataSchema, UploadRequestSchema, SheetMetadataResponseObject, SheetMetadataSchema, ColumnDataSchema, \
    SheetDataResponseObject, FilterSchema, SheetUpdateRequestSchema, CustomColumnDataSchema
import logging
from django.http import HttpResponse, JsonResponse

from clinical_analytics.schemas import StatusEnum

api = NinjaAPI(urls_namespace="data_import")

logger = logging.getLogger(__name__)


def get_user_id(request, response):
    token = request.COOKIES.get("jwt")

    if not token:
        token = request.headers.get("Authorization")
        if not token:
            logger.error("No token found in the request")
            response.messages.append("Authentication failed, please login to continue")
            response.status = StatusEnum.FAILURE
            return JsonResponse(response.dict(), status=401)
        else:
            token = token.split(" ")[1]
    token = token.replace('"', '')
    try:
        payload = jwt.decode(token, 'secret', algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        logger.error("Token expired")
        response.messages.append("Token expired, please login to continue")
        response.status = StatusEnum.FAILURE
        return JsonResponse(response.dict(), status=401)
    except jwt.InvalidTokenError:
        logger.error("Invalid token")
        response.messages.append("Invalid token, please login to continue")
        response.status = StatusEnum.FAILURE
        return JsonResponse(response.dict(), status=401)
    except Exception as e:
        logger.error("Error decoding token: {}".format(e))
        response.messages.append("Error decoding token: {}".format(e))
        response.status = StatusEnum.FAILURE
        return JsonResponse(response.dict(), status=401)

    return payload.get("user_id")


@api.post("/import_data", response=ZipUploadResponseObject, tags=["Data Import"])
def import_data(request, data_file: File[UploadedFile], payload: Form[UploadRequestSchema]):
    logger.info("Importing data")
    zip_upload_response = ZipUploadResponseObject()
    user_id = get_user_id(request, zip_upload_response)
    if isinstance(user_id, JsonResponse):
        return user_id
    sheet_upload_response = SheetUploadResponseObject()
    file_obj = data_file.read()
    if not file_obj:
        logger.error("File not found in the request")
        zip_upload_response.messages.append("No file found in the request")
        zip_upload_response.status = StatusEnum.FAILURE
        return JsonResponse(zip_upload_response.dict(), status=400)

    study_id = payload.study_id
    if not study_id:
        logger.error("Study Data not found in the request")
        zip_upload_response.messages.append("Study data not found in the request")
        zip_upload_response.status = StatusEnum.FAILURE
        return JsonResponse(zip_upload_response.dict(), status=400)
    zip_file_id = payload.zip_file_id
    sheet_id = payload.sheet_id
    file_name = data_file.name
    if sheet_id and file_name.endswith('.zip'):
        logger.error("Invalid file type for versioning a file. Only CSV and XLSX files are supported.")
        zip_upload_response.messages.append(
            "Invalid file type for versioning a file. Only CSV and XLSX files are supported.")
        zip_upload_response.status = StatusEnum.FAILURE
        return JsonResponse(zip_upload_response.dict(), status=400)

    if zip_file_id and not file_name.endswith('.zip'):
        logger.error("Invalid file type for versioning a bunch of files. Only ZIP files are supported.")
        zip_upload_response.messages.append(
            "Invalid file type for versioning a bunch of files. Only ZIP files are supported.")
        zip_upload_response.status = StatusEnum.FAILURE
        return JsonResponse(zip_upload_response.dict(), status=400)
    # user = request.user  # Assuming you have user authentication in place

    # Generate a unique file name for storage
    blob_name = "{}_{}".format(uuid.uuid4(), file_name)

    # Upload file to Azure Storage
    try:
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=settings.AZURE_STORAGE_CONTAINER_NAME,
                                                          blob=blob_name)
        blob_client.upload_blob(file_obj)
        logger.info("File uploaded to Azure Storage")
    except AzureError as e:
        logger.error("AzureError while uploading file to Azure Storage: {}".format(e))
        zip_upload_response.messages.append("AzureError uploading file to Azure Storage: {}".format(e))
        zip_upload_response.status = StatusEnum.FAILURE
        return JsonResponse(zip_upload_response.dict(), status=500)
    except Exception as e:
        logger.error("Error while uploading file to Azure Storage: {}".format(e))
        zip_upload_response.messages.append("Error while uploading file to Azure Storage: {}".format(e))
        zip_upload_response.status = StatusEnum.FAILURE
        return JsonResponse(zip_upload_response.dict(), status=500)

    # Generate URL for the uploaded file
    date_lake_url = blob_client.blob_name

    # Save file upload details to the database
    if zip_file_id or file_name.endswith('.zip'):
        zip_upload_data = None
        if zip_file_id:
            zip_upload_data = ZipUploadData.objects.get(id=zip_file_id)
            if not zip_upload_data:
                logger.error("Invalid file id for versioning a bunch of files")
                zip_upload_response.messages.append("Invalid file id for versioning a bunch of files")
                zip_upload_response.status = StatusEnum.FAILURE
                return JsonResponse(zip_upload_response.dict(), status=400)
        version_number = zip_upload_data.version_number + 1 if zip_upload_data else 1
        zip_upload_data = ZipUploadData.objects.create(
            uploaded_by_id=user_id,
            study_id=study_id,
            original_file_name=file_name,
            date_lake_url=date_lake_url,
            status=DataImportStatusEnum.UPLOADED,
            version_number=version_number
        )
        logger.info("zip file metadata saved to the database")
        logger.info("Starting the file processing tasks for the zip file with id {}".format(zip_upload_data.id))
        chain(download_file.s(zip_upload_data.id, None).set(queue='tasks'),
              process_zip_file.s(zip_upload_data.id).set(queue='tasks'),
              process_csv_file.s(zip_upload_data.id, None).set(queue='tasks')).apply_async()
        zip_upload_response.status = StatusEnum.SUCCESS
        zip_upload_response.data = ZipUploadDataSchema.model_validate(zip_upload_data)
        return JsonResponse(zip_upload_response.dict())
    elif file_name.endswith('.csv') or file_name.endswith('.xlsx'):
        sheet_upload_data = None
        if sheet_id:
            sheet_upload_data = SheetUploadData.objects.get(id=sheet_id)
            if not sheet_upload_data:
                logger.error("Invalid file id for versioning a file")
                zip_upload_response.messages.append("Invalid file id for versioning a file")
                zip_upload_response.status = StatusEnum.FAILURE
                return JsonResponse(zip_upload_response.dict(), status=400)

        csv_version_number = sheet_upload_data.version_number + 1 if sheet_upload_data else 1
        ref = uuid.uuid4()
        sheet_data = SheetUploadData.objects.create(
            zip_upload_id=sheet_upload_data.zip_upload_id if sheet_upload_data else None,
            study_id=study_id,
            original_file_name=file_name,
            date_lake_url=date_lake_url,
            unique_reference=ref,
            version_number=csv_version_number,
            status=DataImportStatusEnum.UPLOADED,
            uploaded_by_id=user_id,
            active=False
        )
        logger.info("sheet metadata saved to the database")
        logger.info("Starting the file processing tasks for the sheet with id {}".format(sheet_data.id))
        chain(
            download_file.s(None, sheet_data.id).set(queue='tasks'),
            wrapper_process_csv_file.s().set(queue='tasks')
        ).apply_async()
        sheet_upload_response.status = StatusEnum.SUCCESS
        sheet_upload_response.data = SheetUploadDataSchema.model_validate(sheet_data)
        return JsonResponse(sheet_upload_response.dict())
    else:
        logger.error("Invalid file type. Only ZIP, CSV, and XLSX files are supported.")
        zip_upload_response.status = StatusEnum.FAILURE
        zip_upload_response.messages.append("Invalid file type. Only ZIP, CSV, and XLSX files are supported.")
        return JsonResponse(zip_upload_response.dict(), status=400)


@api.post("/study", response=StudyDataResponseObject, tags=["Study Data"])
def create_study(request, payload: StudyDataSchema):
    logger.info("Creating study")
    study_response = StudyDataResponseObject(status=StatusEnum.FAILURE)
    study_name = payload.study_name
    sponsor_name = payload.sponsor_name
    alias = payload.alias
    if not study_name:
        logger.error("Study name not found in the request")
        study_response.messages.append("Study name not found in the request")
        study_response.status = StatusEnum.FAILURE
        return JsonResponse(study_response.dict(), status=400)
    user_id = get_user_id(request, study_response)
    if isinstance(user_id, JsonResponse):
        return user_id
    study_data = StudyData.objects.create(
        user_id=user_id,
        study_name=study_name,
        sponsor_name=sponsor_name,
        alias=alias
    )
    logger.info("Study metadata saved to the database")
    study_response.status = StatusEnum.SUCCESS
    study_response.data = StudyDataSchema.model_validate(study_data)
    return JsonResponse(study_response.dict(), status=201, safe=False)


@api.get("/study", response=StudyListResponseObject, tags=["Study Data"])
def get_studies(request):
    logger.info("Getting studies for which user has access to")
    study_response = StudyListResponseObject()
    user_id = get_user_id(request, study_response)
    if isinstance(user_id, JsonResponse):
        return user_id
    study_data = StudyData.objects.filter(user_id=user_id)
    logger.info("Retrieved {} studies from the database".format(len(study_data)))
    if len(study_data) == 0:
        study_response.status = StatusEnum.FAILURE
        study_response.messages.append("No studies found for your account")
        return JsonResponse(study_response.dict(), status=200, safe=False)

    studies_list = [StudyDataSchema.model_validate(study) for study in study_data]

    study_response.status = StatusEnum.SUCCESS
    study_response.data = studies_list
    return JsonResponse(study_response.dict(), status=200, safe=False)


@api.get("/study/{study_id}", response=SingleStudyResponseObject, tags=["Study Data"])
def get_study(request, study_id: uuid.UUID):
    logger.info("Getting study with id {}".format(study_id))
    study_response = SingleStudyResponseObject()
    user_id = get_user_id(request, study_response)
    if isinstance(user_id, JsonResponse):
        return user_id
    study_data = StudyData.objects.get(user_id=user_id, id=study_id)
    if not study_data:
        logger.error("No study found with id {}".format(study_id))
        study_response.status = StatusEnum.FAILURE
        study_response.messages.append("No study found with id {}".format(study_id))
        return HttpResponse(study_response, status=404)

    logger.info("Retrieved study data and sheet uploads from the database")
    sheet_uploads = SheetUploadData.objects.filter(study_id=study_id)
    logger.info("Retrieved {} sheet uploads for the study with id {}".format(len(sheet_uploads), study_id))
    study_response.status = StatusEnum.SUCCESS
    sheet_list = [SheetUploadDataSchema.model_validate(sheet) for sheet in sheet_uploads]
    study_response.data = SingleStudyDataSchema(StudyDataSchema.model_validate(study_data), sheet_list)
    return JsonResponse(study_response.dict(), status=200, safe=False)


@api.get("/sheet/{sheet_id}/meta_data", response=SheetMetadataResponseObject, tags=["Study Data"])
def get_sheet_meta_data(request, sheet_id: uuid.UUID):
    logger.info("Fetching meta data for sheet with id {}".format(sheet_id))
    meta_data_response = SheetMetadataResponseObject()
    sheet_meta_schema = SheetMetadataSchema()
    user_id = get_user_id(request, sheet_meta_schema)
    if isinstance(user_id, JsonResponse):
        return user_id
    sheet_data = SheetUploadData.objects.get(id=sheet_id)
    if not sheet_data:
        logger.error("No sheet found with id {}".format(sheet_id))
        meta_data_response.status = StatusEnum.FAILURE
        meta_data_response.messages.append("No sheet found with id {}".format(sheet_id))
        return JsonResponse(meta_data_response.dict(), status=404, safe=False)

    aggregation_pipeline = [
        {'$match': {'sql_ref': sheet_data.unique_reference}},
        {'$unwind': '$column_data'},
        {'$sort': {'column_data.column_index': 1}},
        {'$group': {
            '_id': '$_id',
            'column_data': {'$push': '$column_data'}
        }},
    ]
    sheet_meta_data = list(SheetMetaData.objects.aggregate(aggregation_pipeline))
    logger.info("Retrieved sheet meta data from the database for sheet with id {}".format(sheet_data.unique_reference))
    if not sheet_meta_data:
        logger.error("No sheet meta data found for sheet with id {}".format(sheet_id))
        meta_data_response.status = StatusEnum.FAILURE
        meta_data_response.messages.append("No sheet meta data found for sheet with id {}".format(sheet_id))
        return JsonResponse(meta_data_response.dict(), status=404, safe=False)
    sheet_meta_schema.sql_ref = sheet_data.unique_reference
    logger.info(sheet_meta_data[0])
    sheet_meta_schema.column_data = [ColumnDataSchema.model_validate(column) for column in
                                     sheet_meta_data[0].get('column_data',[])]
    sheet_meta_schema.sheet_data = SheetUploadDataSchema.model_validate(sheet_data)
    meta_data_response.data = sheet_meta_schema
    meta_data_response.status = StatusEnum.SUCCESS
    logger.info("Retrieved sheet meta data from the database")
    return JsonResponse(meta_data_response.dict(), status=200, safe=False)


@api.get("/sheet/{sheet_id}", response=SheetDataResponseObject, tags=["Study Data"])
def get_sheet_data(request, sheet_id: uuid.UUID, page: int = 1, page_size: int = 1000):
    logger.info("Fetching data for sheet with id {}".format(sheet_id))
    sheet_response = SheetDataResponseObject()
    user_id = get_user_id(request, sheet_response)
    if isinstance(user_id, JsonResponse):
        return user_id
    sheet_data = SheetUploadData.objects.get(id=sheet_id)
    if not sheet_data:
        logger.error("No sheet found with id {}".format(sheet_id))
        sheet_response.status = StatusEnum.FAILURE
        sheet_response.messages.append("No sheet found with id {}".format(sheet_id))
        return JsonResponse(sheet_response.dict(), status=404, safe=False)
    logger.info("Retrieved sheet data from the database")
    skip = (page - 1) * page_size
    pipeline = [
        {"$match": {"sql_ref": f"{sheet_data.unique_reference}"}},
        {"$unwind": "$data"},
        {"$skip": skip},
        {"$limit": page_size},
        {"$replaceRoot": {"newRoot": "$data"}},

    ]
    results = MongoDbClient.objects.aggregate(pipeline)
    combined_data = list(results)
    logger.info("Retrieved data of length {} from the database".format(len(combined_data)))
    if not combined_data:
        logger.error("No sheet found with id {}".format(sheet_id))
        sheet_response.status = StatusEnum.FAILURE
        sheet_response.messages.append("No sheet found with id {}".format(sheet_id))
        return JsonResponse(sheet_response.dict(), status=404, safe=False)
    logger.info("Retrieved sheet data from the database")
    sheet_response.data = combined_data
    sheet_response.status = StatusEnum.SUCCESS

    return JsonResponse(sheet_response.dict(), status=200, safe=False)


@api.post("/sheet/{sheet_id}/filters", response=SheetDataResponseObject, tags=["Study Data"])
def apply_sheet_filters(request, sheet_id: uuid.UUID, filter_data: FilterSchema, page: int = 1, page_size: int = 1000):
    logger.info("Applying filters to sheet with id {}".format(sheet_id))
    sheet_response = SheetDataResponseObject()
    user_id = get_user_id(request, sheet_response)
    if isinstance(user_id, JsonResponse):
        return user_id
    sheet_data = SheetUploadData.objects.get(id=sheet_id)
    if not sheet_data:
        logger.error("No sheet found with id {}".format(sheet_id))
        sheet_response.status = StatusEnum.FAILURE
        sheet_response.messages.append("No sheet found with id {}".format(sheet_id))
        return JsonResponse(sheet_response.dict(), status=404, safe=False)
    logger.info("Retrieved sheet data from the database")

    match_conditions = generate_match_query(filter_data)

    pipeline = [
        {"$match": {"sql_ref": f"{sheet_data.unique_reference}"}},
        {"$unwind": "$data"},
    ]
    if match_conditions and len(match_conditions) > 0:
        pipeline.append({"$match": match_conditions})
        logger.info(
            "Generated match conditions for the filters and sorting parameters for sheet with id {}".format(sheet_id))
    if len(filter_data.sort_by_column) > 0:
        sort_conditions = sorting_query(filter_data)
        pipeline.append({"$sort": sort_conditions})
        logger.info(
            "Generated sort conditions for the filters and sorting parameters for sheet with id {}".format(sheet_id))
    skip = (page - 1) * page_size
    pipeline.append({"$skip": skip})
    pipeline.append({"$limit": page_size})
    pipeline.append({"$replaceRoot": {"newRoot": "$data"}})

    results = MongoDbClient.objects.aggregate(pipeline)
    combined_data = list(results)
    logger.info("Retrieved data of length {} from the database".format(len(combined_data)))
    if not combined_data:
        logger.error("No sheet found with id {}".format(sheet_id))
        sheet_response.status = StatusEnum.FAILURE
        sheet_response.messages.append("No sheet found with id {}".format(sheet_id))
        return JsonResponse(sheet_response.dict(), status=404, safe=False)
    logger.info("Retrieved sheet data from the database")
    sheet_response.data = combined_data
    sheet_response.status = StatusEnum.SUCCESS

    return JsonResponse(sheet_response.dict(), status=200, safe=False)


def generate_match_query(filter_data):
    operators_map = {
        "equals": "$eq",
        "not equals": "$ne",
        "greater than": "$gt",
        "less than": "$lt",
        "greater than equals": "$gte",
        "less than equals": "$lte",
    }

    match_conditions = {}
    for column, value, method in zip(filter_data.filter_column, filter_data.value, filter_data.filter_method):
        operator = operators_map.get(method.lower())
        if operator:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    value = value

            condition = {operator: value}
            match_conditions[f"data.{column}"] = condition

    return match_conditions


def sorting_query(filter_schema):
    sort_conditions = {}
    for column, order in zip(filter_schema.sort_by_column, filter_schema.sort_order):
        sort_conditions[f"data.{column}"] = order

    return sort_conditions


@api.post("/sheet/{sheet_id}/update", response=SheetDataResponseObject, tags=["Study Data"])
def update_sheet_data_api(request, sheet_id: uuid.UUID, payload: list[SheetUpdateRequestSchema]):
    logger.info("Updating sheet with id {}".format(sheet_id))
    sheet_response = SheetDataResponseObject()
    user_id = get_user_id(request, sheet_response)
    if isinstance(user_id, JsonResponse):
        return user_id
    sheet_data = SheetUploadData.objects.get(id=sheet_id)
    if not sheet_data:
        logger.error("No sheet found with id {}".format(sheet_id))
        sheet_response.status = StatusEnum.FAILURE
        sheet_response.messages.append("No sheet found with id {}".format(sheet_id))
        return JsonResponse(sheet_response.dict(), status=404, safe=False)

    logger.info("Retrieved sheet data from the database")
    try:
        for update_sheet_data in payload:
            column_name = update_sheet_data.name
            meta_data = SheetMetaData.objects.get(sql_ref=sheet_data.unique_reference)
            if update_sheet_data.newcolumn:
                logger.info("Error sheet")
                index = int(update_sheet_data.column_index)
                protected = False
                if update_sheet_data.input_type == "FOR":
                    protected = True
                new_column_data = ColumnData(
                    name=column_name,
                    column_index=index,
                    input_type=update_sheet_data.input_type,
                    formula_string=update_sheet_data.formula_string,
                    protected=protected,
                    data_type=update_sheet_data.data_type,
                    alphabet=chr(ord('A')+index)
                )
                # logger.info("Index" + index)

                updated_column_data = []
                for data in meta_data.column_data:
                    if data.column_index >= index:
                        data.column_index += 1
                        data.alphabet = chr(ord(data.alphabet) + 1)
                    updated_column_data.append(data)
                updated_column_data.append(new_column_data)
                meta_data.column_data = updated_column_data
                logger.info(updated_column_data)
                meta_data.save()
            # else:
            #     column_data = column_data_list[0]

            if update_sheet_data.input_type == "FOR":
                continue
            else:
                update_operations = []
                for updated_data in update_sheet_data.updated_data:
                    sct_id = updated_data.sct_id
                    value = updated_data.value
                    filters = {
                        "sql_ref": f"{sheet_data.unique_reference}",
                        "data.sct_id": sct_id
                    }
                    update = {"$set": {"data.$.{}".format(column_name): value}}

                    update_operations.append(pymongo.UpdateOne(filters, update))

                logger.info(update_operations)
                if update_operations:
                    MongoDbClient._get_collection().bulk_write(update_operations, ordered=False)
    except Exception as e:
        logger.error("Error updating sheet data: {}".format(e))
        sheet_response.status = StatusEnum.FAILURE
        sheet_response.messages.append("Error updating sheet data: {}".format(e))
        return JsonResponse(sheet_response.dict(), status=500, safe=False)
    logger.info("Sheet data updated successfully")
    sheet_response.status = StatusEnum.SUCCESS
    sheet_response.messages.append("Sheet data updated successfully")
    return JsonResponse(sheet_response.dict(), status=200, safe=False)


@api.get("/sheet/{sheet_id}/custom_columns", response=SheetDataResponseObject, tags=["Study Data"])
def get_custom_columns(request, sheet_id: uuid.UUID):
    logger.info("Fetching custom columns for sheet with id {}".format(sheet_id))
    sheet_response = SheetDataResponseObject()
    user_id = get_user_id(request, sheet_response)
    if isinstance(user_id, JsonResponse):
        return user_id
    sheet_data = SheetUploadData.objects.get(id=sheet_id)
    if not sheet_data:
        logger.error("No sheet found with id {}".format(sheet_id))
        sheet_response.status = StatusEnum.FAILURE
        sheet_response.messages.append("No sheet found with id {}".format(sheet_id))
        return JsonResponse(sheet_response.dict(), status=404, safe=False)

    logger.info("Retrieved sheet data from the database")
    custom_columns = CustomColumnData.objects.filter(sheet_id=sheet_id)
    if not custom_columns or len(custom_columns) == 0:
        logger.info("No custom columns found for sheet with id {}".format(sheet_id))
        sheet_response.status = StatusEnum.SUCCESS
        sheet_response.messages.append("No custom columns found for sheet with id {}".format(sheet_id))
        return JsonResponse(sheet_response.dict(), status=200, safe=False)

    logger.info("Retrieved {} custom columns for the sheet with id {}".format(len(custom_columns), sheet_id))
    sheet_response.status = StatusEnum.SUCCESS
    sheet_response.data = [CustomColumnDataSchema.model_validate(column) for column in custom_columns]
    return JsonResponse(sheet_response.dict(), status=200, safe=False)
