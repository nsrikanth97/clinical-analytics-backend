from typing import Optional
from uuid import UUID

from pydantic import BaseModel, validator, field_validator, EmailStr
import re
from datetime import datetime
from clinical_analytics.schemas import ResponseObject


class UserDataSchema(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: str

    # @field_validator('password')
    # @classmethod
    # def password_strong(cls, v):
    #     # Minimum eight characters, at least one uppercase letter, one lowercase letter, one number and one special character
    #     password_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    #     if not re.match(password_regex, v):
    #         raise ValueError(
    #             "Password must be at least 8 characters long, include an uppercase letter, a lowercase letter, a number, and a special character.")
    #     return v

    @field_validator('email')
    @classmethod
    def email_lowercase(cls, v):
        return v.lower()

    @field_validator('first_name', 'last_name')
    @classmethod
    def name_validator(cls, v, field):
        if not v.strip():
            raise ValueError(f"{field.name} cannot be empty or just whitespace.")
        if len(v) < 2:
            raise ValueError(f"{field.name} must be more than 1 character.")
            # Additional checks can be added here (e.g., regex for allowed characters)
        if len(v) > 16:
            raise ValueError(f"{field.name} must be less than 16 characters.")
        valid_regex = r"^[a-zA-Z]+$"
        if not re.match(valid_regex, v):
            raise ValueError(f"{field.name} must only contain letters.")
        return v

    class Config:
        from_attributes = True


class UserResponseSchema(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    mfa_enabled: bool
    date_joined: datetime
    password_last_changed: datetime
    token: Optional[str]

    class Config:
        from_attributes = True


class LoginSchema(BaseModel):
    email: EmailStr
    password: str

    @field_validator('email')
    @classmethod
    def email_lowercase(cls, v):
        return v.lower()

    class Config:
        from_attributes = True


UserResponseObject = ResponseObject[UserResponseSchema]

