"""Consistent sanitized error responses for the local web API."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "LOGIN_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "JOB_CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    502: "NHSO_UNAVAILABLE",
    503: "SERVICE_UNAVAILABLE",
}


def error_response(status_code: int, code: str, message: str, details=None):
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": error},
    )


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "ไม่สามารถดำเนินการได้"
        return error_response(
            exc.status_code,
            STATUS_CODES.get(exc.status_code, "REQUEST_ERROR"),
            message,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(part) for part in item["loc"] if part != "body"),
                "message": item["msg"],
            }
            for item in exc.errors()
        ]
        return error_response(
            422,
            "VALIDATION_ERROR",
            "ข้อมูลที่ระบุไม่ถูกต้อง",
            details,
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, _exc: Exception):
        return error_response(
            500,
            "INTERNAL_ERROR",
            "ระบบไม่สามารถดำเนินการได้",
        )
