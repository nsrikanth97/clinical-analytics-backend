import datetime
import jwt
import logging

from django.http import JsonResponse
from ninja import NinjaAPI
from pydantic import ValidationError

from clinical_analytics.schemas import ResponseObject
from .models import User
from .schemas import UserDataSchema, UserResponseObject, UserResponseSchema, LoginSchema

api = NinjaAPI(urls_namespace="authentication")
logger = logging.getLogger(__name__)


@api.exception_handler(ValidationError)
def exception_handler(request, exc):
    response_object = ResponseObject()
    if isinstance(exc, ValidationError):
        response_object.status = "FAILURE"
        response_object.messages.append("Validation error")
        response_object.messages.append(str(exc))
        return JsonResponse(response_object.dict(), status=422)
    else:
        response_object.status = "FAILURE"
        response_object.messages.append("Internal server error")
        response_object.messages.append(str(exc))
        return JsonResponse(response_object.dict(), status=500)


@api.post("/register", response=UserResponseObject, tags=["auth"])
def register(request, user_data: UserDataSchema):
    logger.info(f"Registering  user with email {user_data.email}")
    response = UserResponseObject()
    try:
        user = User.objects.create(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            is_active=False,
        )
        user.set_password(user_data.password)
        user.password_last_changed = user.date_joined
        user.save()
        logger.info(f"User {user.email} created successfully.")
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        response.status = "FAILURE"
        response.messages.append("Error creating user account.")
        response.messages.append(str(e))
        return JsonResponse(response.dict(), status=500)

    response.status = "SUCCESS"
    response.data = UserResponseSchema.model_validate(user)
    return JsonResponse(response.dict(), status=201)


@api.post("/login", response=UserResponseObject, tags=["auth"])
def login(request, user_data: LoginSchema):
    logger.info(f"Logging in user with email {user_data.email}")
    response = ResponseObject()
    try:
        user = User.objects.get(email=user_data.email)
        logger.info(f"User {user.email} found.")
        if user.check_password(user_data.password):
            logger.info(f"User {user.email} authenticated successfully.")
            user_id = str(user.id)
            payload = {
                "user_id": user_id,
                "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=60),
                "iat": datetime.datetime.now(datetime.UTC)
            }
            token = jwt.encode(payload, 'secret', algorithm='HS256')
            user.token = token
            logger.info(f"User {user.email} token generated successfully.")
            response.status = "SUCCESS"
            response.data = UserResponseSchema.model_validate(user)
            json_response = JsonResponse(response.dict(), status=200)
            user.last_login = datetime.datetime.now(datetime.UTC)
            user.save()
            json_response.set_cookie("jwt", token, httponly=True)
            return json_response
        else:
            user.failed_login_attempts += 1
            user.save()
            response.status = "FAILURE"
            logger.warning(f"User {user.email} failed to authenticate.")
            response.messages.append("Invalid email or password.")
            return JsonResponse(response.dict(), status=401)
    except User.DoesNotExist:
        response.status = "FAILURE"
        logger.warning(f"User {user_data.email} not found.")
        response.messages.append("Invalid email or password.")
        return JsonResponse(response.dict(), status=401)
    except Exception as e:
        logger.error(f"Error logging in user: {e}")
        response.status = "FAILURE"
        response.messages.append("Internal server error")
        response.messages.append(str(e))
        return JsonResponse(response.dict(), status=500)


@api.get("/logout", tags=["auth"])
def logout(request):
    response = ResponseObject()
    response.status = "SUCCESS"
    json_response = JsonResponse(response.dict(), status=200)
    json_response.delete_cookie("jwt")
    return json_response
