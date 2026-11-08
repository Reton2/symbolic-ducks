from fastapi import APIRouter
from fastapi.responses import FileResponse

root_router = APIRouter()


@root_router.get("/")
async def index() -> FileResponse:
    return FileResponse("static/index.html")
