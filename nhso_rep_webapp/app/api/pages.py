"""Server-rendered web pages."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from ..services.rep_service import get_default_destination


templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
router = APIRouter(include_in_schema=False)


@router.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"default_destination": get_default_destination()},
    )
