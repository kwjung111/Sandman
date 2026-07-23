import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from . import database as db
from .ncp_client import ncp_client, NCPApiError

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# 앱 재시작·지연으로 트리거 시각을 놓쳐도 이 시간 안이면 실행 (초)
MISFIRE_GRACE_SEC = 600
# NCP API 실패 시 재시도 간격(분)과 최대 시도 횟수
RETRY_DELAY_MINUTES = 5
MAX_ATTEMPTS = 3


def is_work_time(group: dict) -> bool:
    """해당 그룹 기준으로 현재가 업무 시간인지 확인"""
    now = datetime.now()

    if not group["include_weekends"] and now.weekday() >= 5:
        return False

    current_minutes = now.hour * 60 + now.minute
    start_minutes = group["start_hour"] * 60 + group["start_minute"]
    end_minutes = group["end_hour"] * 60 + group["end_minute"]

    return start_minutes <= current_minutes < end_minutes


def is_weekend() -> bool:
    return datetime.now().weekday() >= 5


def get_status_info() -> dict:
    """그룹별 업무시간 상태 + 현재 시각"""
    assignments = db.get_assignments()
    groups = []
    for g in db.list_groups():
        server_count = sum(1 for gid in assignments.values() if gid == g["id"])
        groups.append({
            **g,
            "include_weekends": bool(g["include_weekends"]),
            "is_work_time": is_work_time(g),
            "server_count": server_count,
        })
    return {
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "auto_stop_enabled": db.auto_stop_enabled(),
        "groups": groups,
    }


async def _get_group_servers(group_id: int) -> list[dict]:
    """필터링된 전체 서버 중 해당 그룹에 할당된 서버만 반환. NCP 실패 시 NCPApiError 전파"""
    result = await ncp_client.get_server_list()
    server_list = result["getServerInstanceListResponse"]["serverInstanceList"]
    assignments = db.get_assignments()
    return [s for s in server_list if assignments.get(s["serverInstanceNo"]) == group_id]


def _schedule_retry(func, group_id: int, kind: str, attempt: int):
    """NCP API 실패 시 일정 시간 후 재시도 잡 등록 (최대 MAX_ATTEMPTS회)"""
    if attempt >= MAX_ATTEMPTS:
        logger.error(f"[Scheduler] 그룹 {group_id} {kind} {MAX_ATTEMPTS}회 모두 실패 - 재시도 포기")
        return
    run_at = datetime.now() + timedelta(minutes=RETRY_DELAY_MINUTES)
    scheduler.add_job(
        func, "date", run_date=run_at,
        args=[group_id, attempt + 1],
        id=f"group_{group_id}_{kind}_retry", replace_existing=True,
    )
    logger.warning(
        f"[Scheduler] 그룹 {group_id} {kind} 실패 - {RETRY_DELAY_MINUTES}분 후 재시도 "
        f"({attempt + 1}/{MAX_ATTEMPTS})"
    )


async def auto_start_group(group_id: int, attempt: int = 1):
    """그룹 업무 시작 시간: 해당 그룹 서버 자동 시작 (실패 시 재시도)"""
    group = db.get_group(group_id)
    if not group:
        logger.warning(f"[Scheduler] 그룹 {group_id} 없음 - 시작 건너뜀")
        return

    if not group["include_weekends"] and is_weekend():
        logger.info(f"[Scheduler] 주말이므로 '{group['name']}' 자동 시작을 건너뜁니다.")
        return

    try:
        logger.info(f"[Scheduler] '{group['name']}' 업무 시작 시간 도래 - 서버 시작 프로세스 가동 (시도 {attempt})")
        servers = await _get_group_servers(group_id)

        if not servers:
            logger.info(f"[Scheduler] '{group['name']}' 할당된 서버 없음")
            return

        stopped_ids = [s["serverInstanceNo"] for s in servers
                       if s["serverInstanceStatus"]["code"] in ("NSTOP", "STOP")]

        if stopped_ids:
            logger.info(f"[Scheduler] '{group['name']}' 서버 시작 요청: {stopped_ids}")
            await ncp_client.start_server(stopped_ids)
        else:
            logger.info(f"[Scheduler] '{group['name']}' 모든 서버가 이미 실행 중입니다.")

    except NCPApiError as e:
        logger.error(f"[Scheduler] '{group['name']}' 시작 프로세스 NCP API 오류: {e}")
        _schedule_retry(auto_start_group, group_id, "start", attempt)
    except Exception as e:
        logger.exception(f"[Scheduler] '{group['name']}' 시작 프로세스 오류: {e}")


async def weekend_stop_sweep():
    """주말 스위프: '주말 전체 중지'(include_weekends=0) 그룹의 실행 중 서버를 매시 정각에 중지.

    주말 정책이 '항상 중지'이므로, 수동으로 켠 서버도 다음 스위프에서 다시 꺼진다.
    실패해도 별도 재시도 없음 — 1시간 뒤 다음 스위프가 자연 재시도 역할을 한다.
    """
    if not is_weekend():
        return

    if not db.auto_stop_enabled():
        logger.info("[Scheduler] 자동 중지 기능이 꺼져 있어 주말 스위프를 건너뜁니다.")
        return

    stop_group_ids = {g["id"]: g["name"] for g in db.list_groups() if not g["include_weekends"]}
    if not stop_group_ids:
        return

    try:
        result = await ncp_client.get_server_list()
        server_list = result["getServerInstanceListResponse"]["serverInstanceList"]
        assignments = db.get_assignments()

        targets = [s["serverInstanceNo"] for s in server_list
                   if assignments.get(s["serverInstanceNo"]) in stop_group_ids
                   and s["serverInstanceStatus"]["code"] == "RUN"]

        if targets:
            logger.info(f"[Scheduler] 주말 전체 중지 스위프 - 서버 중지: {targets}")
            await ncp_client.stop_server(targets)
        else:
            logger.debug("[Scheduler] 주말 스위프 - 중지할 서버 없음")

    except NCPApiError as e:
        logger.error(f"[Scheduler] 주말 스위프 NCP API 오류 (다음 정각에 재시도됨): {e}")
    except Exception as e:
        logger.exception(f"[Scheduler] 주말 스위프 오류: {e}")


async def auto_stop_group(group_id: int, attempt: int = 1):
    """그룹 업무 종료 시간: 해당 그룹 서버 자동 중지 (실패 시 재시도)

    주말 여부와 무관하게 수행한다 — 주말에 수동으로 켠 서버라도
    종료 시각이 되면 꺼져야 비용 절감 목적에 맞는다.
    """
    group = db.get_group(group_id)
    if not group:
        logger.warning(f"[Scheduler] 그룹 {group_id} 없음 - 중지 건너뜀")
        return

    if not db.auto_stop_enabled():
        logger.info(f"[Scheduler] 자동 중지 기능이 꺼져 있어 '{group['name']}' 중지를 건너뜁니다.")
        return

    try:
        logger.info(f"[Scheduler] '{group['name']}' 업무 종료 시간 도래 - 서버 중지 프로세스 가동 (시도 {attempt})")
        servers = await _get_group_servers(group_id)

        if not servers:
            logger.info(f"[Scheduler] '{group['name']}' 할당된 서버 없음")
            return

        running_ids = [s["serverInstanceNo"] for s in servers
                       if s["serverInstanceStatus"]["code"] == "RUN"]

        if running_ids:
            logger.info(f"[Scheduler] '{group['name']}' 서버 중지 요청: {running_ids}")
            await ncp_client.stop_server(running_ids)
        else:
            logger.info(f"[Scheduler] '{group['name']}' 중지할 서버가 없습니다 (이미 정지됨).")

    except NCPApiError as e:
        logger.error(f"[Scheduler] '{group['name']}' 중지 프로세스 NCP API 오류: {e}")
        _schedule_retry(auto_stop_group, group_id, "stop", attempt)
    except Exception as e:
        logger.exception(f"[Scheduler] '{group['name']}' 중지 프로세스 오류: {e}")


async def check_and_manage_servers() -> dict:
    """수동 동기화: 모든 그룹을 각자의 시간 규칙에 맞춰 상태 동기화.

    결과 요약을 반환하고, 서버 목록 조회 자체가 실패하면 NCPApiError를 전파한다.
    """
    summary = {"started": 0, "stopped": 0, "stop_skipped": False, "errors": []}

    result = await ncp_client.get_server_list()
    server_list = result["getServerInstanceListResponse"]["serverInstanceList"]
    assignments = db.get_assignments()

    for group in db.list_groups():
        servers = [s for s in server_list if assignments.get(s["serverInstanceNo"]) == group["id"]]
        if not servers:
            continue

        try:
            if is_work_time(group):
                targets = [s["serverInstanceNo"] for s in servers
                           if s["serverInstanceStatus"]["code"] in ("NSTOP", "STOP")]
                if targets:
                    logger.info(f"[Manual] '{group['name']}' 업무 시간 - 서버 시작: {targets}")
                    await ncp_client.start_server(targets)
                    summary["started"] += len(targets)
            else:
                if not db.auto_stop_enabled():
                    logger.info(f"[Manual] 자동 중지 기능이 꺼져 있어 '{group['name']}' 중지를 건너뜁니다.")
                    summary["stop_skipped"] = True
                    continue
                targets = [s["serverInstanceNo"] for s in servers
                           if s["serverInstanceStatus"]["code"] == "RUN"]
                if targets:
                    logger.info(f"[Manual] '{group['name']}' 업무 외 시간 - 서버 중지: {targets}")
                    await ncp_client.stop_server(targets)
                    summary["stopped"] += len(targets)
        except NCPApiError as e:
            logger.error(f"[Manual] '{group['name']}' 처리 실패: {e}")
            summary["errors"].append(f"{group['name']}: {e}")

    return summary


def reschedule_jobs():
    """DB의 그룹 설정대로 cron 잡 전체 재등록 (그룹 변경 시 호출)"""
    for job in scheduler.get_jobs():
        if job.id.startswith("group_"):
            job.remove()

    for g in db.list_groups():
        scheduler.add_job(
            auto_start_group, "cron",
            hour=g["start_hour"], minute=g["start_minute"],
            args=[g["id"]],
            id=f"group_{g['id']}_start", replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SEC,
        )
        scheduler.add_job(
            auto_stop_group, "cron",
            hour=g["end_hour"], minute=g["end_minute"],
            args=[g["id"]],
            id=f"group_{g['id']}_stop", replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SEC,
        )
        logger.info(
            f"[Scheduler] '{g['name']}' 잡 등록 "
            f"(시작: {g['start_hour']:02d}:{g['start_minute']:02d}, "
            f"종료: {g['end_hour']:02d}:{g['end_minute']:02d}, "
            f"주말: {'포함' if g['include_weekends'] else '제외'})"
        )


def start_scheduler():
    """스케줄러 시작 - 그룹별 시작/종료 시간 트리거 + 주말 스위프"""
    scheduler.start()
    reschedule_jobs()
    # 주말(토·일) 매시 정각: '주말 전체 중지' 그룹의 실행 중 서버 중지
    # (id가 group_ 로 시작하지 않으므로 reschedule_jobs()의 영향을 받지 않음)
    scheduler.add_job(
        weekend_stop_sweep, "cron",
        day_of_week="sat,sun", minute=0,
        id="weekend_sweep", replace_existing=True,
        misfire_grace_time=MISFIRE_GRACE_SEC,
    )
    logger.info("[Scheduler] 스케줄러 시작됨 (주말 스위프 포함)")


def stop_scheduler():
    scheduler.shutdown()
