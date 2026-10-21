import re
from typing import Annotated, Literal

from pydantic import EmailStr, Field, field_validator

from backend.app.anthropometry.schemas import Measurements, StrictSchema

Password = Annotated[str, Field(min_length=12, max_length=128)]


def strong_password(value: str) -> str:
    if not re.search(r"[A-Z]", value) or not re.search(r"[a-z]", value) or not re.search(r"\d", value) or not re.search(r"[^a-zA-Z0-9\s]", value):
        raise ValueError("Use 12+ characters with uppercase, lowercase, a number and a symbol.")
    return value


class Signup(StrictSchema):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: Password
    terms_accepted: Literal[True]
    _password = field_validator("password")(strong_password)


class Login(StrictSchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False


class ForgotPassword(StrictSchema):
    email: EmailStr


class ResetPassword(StrictSchema):
    token: str = Field(min_length=32, max_length=128)
    password: Password
    _password = field_validator("password")(strong_password)


class ProfileUpdate(StrictSchema):
    name: str = Field(min_length=2, max_length=80)
    height_cm: float | None = Field(default=None, ge=80, le=250)


class SaveScan(StrictSchema):
    label: str = Field(default="Body measurements", min_length=1, max_length=80)
    height_cm: float = Field(ge=80, le=250)
    measurements: Measurements
    source: Literal["photo-estimate", "manually-corrected", "manual"]
    thumbnail_base64: str | None = Field(default=None, max_length=500_000)


