import uuid
from typing import List, Optional, Any

from ninja import File, UploadedFile
from pydantic import BaseModel, Field, model_validator
from .models import DataImportStatusEnum
from clinical_analytics.schemas import ResponseObject
from uuid import UUID
from datetime import datetime


class UploadRequestSchema(BaseModel):
    study_id: UUID
    zip_file_id: Optional[UUID] = None
    sheet_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class UploadDataSchema(BaseModel):
    id: UUID
    original_file_name: str
    upload_date_time: datetime
    status: DataImportStatusEnum
    additional_info: Optional[str]
    version_number: int
    date_lake_url: Optional[str]
    alias: Optional[str]
    uploaded_by_id: UUID

    class Config:
        from_attributes = True
        json_encoders = {
            DataImportStatusEnum: lambda v: v.value
        }


class ZipUploadDataSchema(UploadDataSchema):
    study_id: UUID


class SheetUploadDataSchema(UploadDataSchema):
    zip_upload_id: Optional[UUID]
    unique_reference: Optional[UUID]
    file_type: Optional[str]
    study_id: UUID
    active: bool


class StudyDataSchema(BaseModel):
    id: Optional[UUID] = Field(default_factory=uuid.uuid4)
    study_name: str
    sponsor_name: str
    alias: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    image: Optional[str] = None

    class Config:
        from_attributes = True


ZipUploadResponseObject = ResponseObject[ZipUploadDataSchema]

SheetUploadResponseObject = ResponseObject[SheetUploadDataSchema]

StudyDataResponseObject = ResponseObject[StudyDataSchema]

StudyListResponseObject = ResponseObject[List[StudyDataSchema]]


class SingleStudyDataSchema(BaseModel):
    study_data: Optional[StudyDataSchema] = None
    sheet_uploads: Optional[List[SheetUploadDataSchema]] = None

    def __init__(self, study_data: StudyDataSchema, sheet_uploads: List[SheetUploadDataSchema], **data: Any):
        super().__init__(**data)
        self.study_data = study_data
        self.sheet_uploads = sheet_uploads


class ColumnDataSchema(BaseModel):
    name: str
    data_type: Optional[str]
    column_index: int
    input_type: str
    formula_string: Optional[str] = None
    format_string: Optional[str] = None
    resizable: bool
    visible: bool
    protected: bool

    class Config:
        from_attributes = True


class SheetMetadataSchema(BaseModel):
    sql_ref: UUID = None
    column_data: List[ColumnDataSchema] = []
    sheet_data: Optional[SheetUploadDataSchema] = None

    class Config:
        from_attributes = True


class SheetDataSchema(BaseModel):
    data: List[dict]

    class Config:
        from_attributes = True


class FilterSchema(BaseModel):
    filter_column: Optional[List[str]] = []
    value: Optional[List[str]] = None
    filter_method: Optional[List[str]] = None
    sort_by_column: Optional[List[str]] = []
    sort_order: Optional[List[int]] = None

    @model_validator(mode="before")
    @classmethod
    def check_required_data(cls, values):
        if not values.get('filter_column') and not values.get('sort_by_column'):
            raise ValueError("At least one filter_column or sort_by_column is required")
        return values

    #
    @model_validator(mode="before")
    @classmethod
    def validate_filter_data(cls, values):
        filter_columns = values.get('filter_column')
        value = values.get('value')
        filter_method = values.get('filter_method')
        if filter_columns:
            if filter_columns and value and filter_method:
                if len(filter_columns) != len(value) or len(filter_columns) != len(filter_method):
                    raise ValueError("filter_column, value and filter_method should have same length")
            else:
                raise ValueError("filter_column, value and filter_method all are required")
        else:
            return values
        for v, method in zip(value, filter_method):
            if method in ["greater than", "less than", "greater than equals", "less than equals"]:
                try:
                    float(v)
                except ValueError:
                    try:
                        int(v)
                    except ValueError:
                        raise ValueError(
                            "Value should be a number for filter method including greater than and less than")
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_sort_data(cls, values):
        sort_by_column = values.get('sort_by_column')
        sort_order = values.get('sort_order')
        if sort_by_column:
            if sort_by_column and sort_order:
                if len(sort_by_column) != len(sort_order):
                    raise ValueError("sort_by_column and sort_order should have same length")
            else:
                raise ValueError("sort_by_column and sort_order both are required")
        else:
            return values
        for order in sort_order:
            if order not in [1, -1]:
                raise ValueError("sort_order should be 1 or -1")
        return values


SingleStudyResponseObject = ResponseObject[SingleStudyDataSchema]

SheetMetadataResponseObject = ResponseObject[SheetMetadataSchema]

SheetDataResponseObject = ResponseObject[SheetDataSchema]


class UpdatedDataSchema(BaseModel):
    sct_id: str
    value: str


class SheetUpdateRequestSchema(BaseModel):
    name: str
    updated_data: List[UpdatedDataSchema]
    column_index: int
    input_type: str
    data_type: Optional[str]
    formula_string: Optional[str] = None
    newcolumn: bool


class CustomColumnDataSchema(BaseModel):
    id: UUID
    sheet_id_id: UUID
    column_name: str
    column_index: int
    created_date_time: datetime
    input_type: str
    formula_string: Optional[str] = None

    class Config:
        from_attributes = True


CustomColumnDataResponseObject = ResponseObject[CustomColumnDataSchema]
