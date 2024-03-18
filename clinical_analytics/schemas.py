from datetime import datetime, timezone
from enum import Enum
from typing import TypeVar, Generic, List, Optional

from pydantic import BaseModel, Field


class StatusEnum(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class SeverityEnum(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class Message(BaseModel):
    text: Optional[str] = Field(..., description="The message text")
    severity: Optional[SeverityEnum] = Field(..., description="The severity level of the message")


T = TypeVar("T", bound=BaseModel)


class ResponseObject(BaseModel, Generic[T]):
    status: StatusEnum = Field(StatusEnum.FAILURE, description="Indicates the success or failure of the request")
    messages: List[str] = Field(default=[],
                                description="Messages, e.g., errors, warnings, informational messages")
    data: Optional[T] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
                                          description="Timestamp of the response")
