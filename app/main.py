from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .ncp_client import ncp_client
from .scheduler import start_scheduler, stop_scheduler, get_work_time_info, check_and_manage_servers
from .config import Config


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="NCP 서버 관리 대시보드", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


class ServerActionRequest(BaseModel):
    server_instance_nos: list[str]


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/status")
async def get_status():
    return {
        "work_time_info": get_work_time_info(),
        "name_filter": Config.SERVER_NAME_FILTER or "(전체)",
        "api_configured": bool(Config.NCP_ACCESS_KEY and Config.NCP_SECRET_KEY)
    }


@app.get("/api/servers")
async def get_servers():
    """서버 목록 조회 (SERVER_NAME_FILTER로 필터링)"""
    try:
        return await ncp_client.get_server_list()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/servers/start")
async def start_servers(request: ServerActionRequest):
    try:
        return await ncp_client.start_server(request.server_instance_nos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/servers/stop")
async def stop_servers(request: ServerActionRequest):
    try:
        return await ncp_client.stop_server(request.server_instance_nos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scheduler/run")
async def run_scheduler_now():
    try:
        await check_and_manage_servers()
        return {"message": "스케줄러 작업 실행 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
