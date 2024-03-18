from django.http import HttpResponse
from pydantic import ValidationError

from clinical_analytics.schemas import ResponseObject
from .api import api


@api.exception_handler(ValidationError)
def exception_handler(request, exc):
    response_object = ResponseObject()
    if isinstance(exc, ValidationError):
        response_object.status = "FAILURE"
        response_object.messages.append("Validation error")
        response_object.messages.append(str(exc))
        return HttpResponse(response_object.dict(), status=422)
    else:
        response_object.status = "FAILURE"
        response_object.messages.append("Internal server error")
        response_object.messages.append(str(exc))
        return HttpResponse(response_object.dict(), status=500)
