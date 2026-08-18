"""Pydantic request and response schemas for the web API."""

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator


class DownloadRequest(BaseModel):
    start_date: date
    end_date: date
    destination: str = Field(min_length=1, max_length=1024)
    overwrite: bool = False
    insecure: bool = False
    hcode: str | None = Field(default=None, pattern=r"^\d{5}$")
    page_size: int = Field(default=3000, ge=1, le=10000)

    @field_validator("destination")
    @classmethod
    def destination_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Destination must not be blank")
        return value

    @model_validator(mode="after")
    def dates_must_be_ordered(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must not be before start date")
        return self


class AuthStatusResponse(BaseModel):
    status: str
    logged_in: bool
    hcode: str | None = None


class AuthLoginResponse(BaseModel):
    success: bool
    status: str


class WebSettings(BaseModel):
    default_destination: str = Field(min_length=1, max_length=1024)
    default_page_size: int = Field(default=3000, ge=1, le=10000)
    default_insecure: bool = False
    last_start_date: date | None = None
    last_end_date: date | None = None

    @field_validator("default_destination")
    @classmethod
    def default_destination_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Default destination must not be blank")
        return value
