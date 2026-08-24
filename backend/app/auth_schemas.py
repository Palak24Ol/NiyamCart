from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name", "email")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = value.lower()
        if normalized.count("@") != 1 or "." not in normalized.split("@", 1)[1]:
            raise ValueError("Enter a valid email address")
        return normalized

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not any(char.islower() for char in value):
            raise ValueError("Password needs a lowercase letter")
        if not any(char.isupper() for char in value):
            raise ValueError("Password needs an uppercase letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password needs a number")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime


class AuthResponse(BaseModel):
    user: CustomerResponse


class LogoutResponse(BaseModel):
    status: str = "signed_out"
