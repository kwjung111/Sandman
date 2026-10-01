import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from . import database as db
from .ncp_client import ncp_client, NCPApiError
from .scheduler import start_scheduler, stop_scheduler, get_status_info, check_and_manage_servers, reschedule_jobs
from .config import Config


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="NCP 서버 관리 대시보드", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path

    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif path in {"/", "/settings"} or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"

    return response


class ServerActionRequest(BaseModel):
    server_instance_nos: list[str]


class GroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    start_hour: int = Field(ge=0, le=23)
    start_minute: int = Field(ge=0, le=59)
    end_hour: int = Field(ge=0, le=23)
    end_minute: int = Field(ge=0, le=59)
    include_weekends: bool = False

    @model_validator(mode="after")
    def check_time_order(self):
        # 자정을 넘는 시간대는 cron 잡과 is_work_time 판정이 어긋나므로 허용하지 않음
        if self.start_hour * 60 + self.start_minute >= self.end_hour * 60 + self.end_minute:
            raise ValueError("종료 시간이 시작 시간보다 늦어야 합니다 (자정을 넘는 시간대는 지원하지 않습니다).")
        return self


class AssignRequest(BaseModel):
    group_id: int | None = None


class SettingsRequest(BaseModel):
    auto_stop_enabled: bool


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/settings")
async def settings_page():
    return FileResponse("static/settings.html")


@app.get("/api/status")
async def get_status():
    return {
        **get_status_info(),
        "name_filter": Config.SERVER_NAME_FILTER or "(전체)",
        "api_configured": bool(Config.NCP_ACCESS_KEY and Config.NCP_SECRET_KEY),
    }


@app.get("/api/servers")
async def get_servers():
    """서버 목록 조회 (이름 필터링 적용, 각 서버에 groupId 부여)"""
    try:
        result = await ncp_client.get_server_list()
    except NCPApiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    server_list = result["getServerInstanceListResponse"]["serverInstanceList"]
    assignments = db.get_assignments()
    for s in server_list:
        s["groupId"] = assignments.get(s["serverInstanceNo"])
    return result


@app.post("/api/servers/start")
async def start_servers(request: ServerActionRequest):
    try:
        return await ncp_client.start_server(request.server_instance_nos)
    except NCPApiError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/servers/stop")
async def stop_servers(request: ServerActionRequest):
    try:
        return await ncp_client.stop_server(request.server_instance_nos)
    except NCPApiError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.put("/api/servers/{server_instance_no}/group")
async def assign_server_group(server_instance_no: str, request: AssignRequest):
    """서버를 그룹에 할당 (group_id=null이면 할당 해제)"""
    if request.group_id is not None and not db.get_group(request.group_id):
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    db.assign_server(server_instance_no, request.group_id)
    return {"server_instance_no": server_instance_no, "group_id": request.group_id}


@app.get("/api/settings")
async def get_settings():
    return {"auto_stop_enabled": db.auto_stop_enabled()}


@app.put("/api/settings")
async def update_settings(request: SettingsRequest):
    db.set_auto_stop_enabled(request.auto_stop_enabled)
    return {"auto_stop_enabled": db.auto_stop_enabled()}


@app.get("/api/groups")
async def get_groups():
    return get_status_info()["groups"]


@app.post("/api/groups")
async def create_group(request: GroupRequest):
    try:
        group = db.create_group(**request.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="같은 이름의 그룹이 이미 있습니다.")
    reschedule_jobs()
    return group


@app.put("/api/groups/{group_id}")
async def update_group(group_id: int, request: GroupRequest):
    if not db.get_group(group_id):
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    try:
        group = db.update_group(group_id, **request.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="같은 이름의 그룹이 이미 있습니다.")
    reschedule_jobs()
    return group


@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: int):
    if not db.delete_group(group_id):
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    reschedule_jobs()
    return {"deleted": group_id}


@app.post("/api/scheduler/run")
async def run_scheduler_now():
    try:
        summary = await check_and_manage_servers()
    except NCPApiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return summary
