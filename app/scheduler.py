import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .config import Config
from .ncp_client import ncp_client

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def is_work_time() -> bool:
    """현재 시간이 업무 시간인지 확인"""
    now = datetime.now()
    weekday = now.weekday()

    if not Config.INCLUDE_WEEKENDS and weekday >= 5:
        return False

    # 현재 시간(분 단위 환산)
    current_minutes = now.hour * 60 + now.minute
    
    # 업무 시작/종료 시간(분 단위 환산)
    start_minutes = Config.WORK_START_HOUR * 60 + Config.WORK_START_MINUTE
    end_minutes = Config.WORK_END_HOUR * 60 + Config.WORK_END_MINUTE
    
    return start_minutes <= current_minutes < end_minutes


def get_work_time_info() -> dict:
    """업무 시간 정보 반환"""
    return {
        "start_hour": Config.WORK_START_HOUR,
        "start_minute": Config.WORK_START_MINUTE,
        "end_hour": Config.WORK_END_HOUR,
        "end_minute": Config.WORK_END_MINUTE,
        "include_weekends": Config.INCLUDE_WEEKENDS,
        "is_work_time": is_work_time(),
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def is_weekend() -> bool:
    """주말 여부 확인"""
    return datetime.now().weekday() >= 5


async def auto_start_servers():
    """업무 시작 시간: 서버 자동 시작"""
    if not Config.INCLUDE_WEEKENDS and is_weekend():
        logger.info("[Scheduler] 주말이므로 자동 시작을 건너뜁니다.")
        return

    try:
        logger.info("[Scheduler] 업무 시작 시간 도래 - 서버 시작 프로세스 가동")
        result = await ncp_client.get_server_list()
        server_list = result.get("getServerInstanceListResponse", {}).get("serverInstanceList", [])

        if not server_list:
            logger.info("[Scheduler] 대상 서버 없음")
            return

        stopped_ids = [s["serverInstanceNo"] for s in server_list
                      if s["serverInstanceStatus"]["code"] in ("NSTOP", "STOP")]
        
        if stopped_ids:
            logger.info(f"[Scheduler] 서버 시작 요청: {stopped_ids}")
            await ncp_client.start_server(stopped_ids)
        else:
            logger.info("[Scheduler] 모든 서버가 이미 실행 중입니다.")

    except Exception as e:
        logger.error(f"[Scheduler] 시작 프로세스 오류: {e}")


async def auto_stop_servers():
    """업무 종료 시간: 서버 자동 중지"""
    # 주말이어도 혹시 켜져 있을 수 있으므로, 주말 제외 옵션이 켜져 있지 않은 이상 끄는 건 수행하는 게 안전할 수 있음.
    # 하지만 사용자가 '주말 포함'을 껐다면 주말엔 아예 동작 안 하는 게 맞을 수도 있음.
    # 여기서는 Config.INCLUDE_WEEKENDS 설정에 따라 주말엔 아예 간섭하지 않도록 처리함.
    if not Config.INCLUDE_WEEKENDS and is_weekend():
        logger.info("[Scheduler] 주말이므로 자동 중지를 건너뜁니다.")
        return

    try:
        logger.info("[Scheduler] 업무 종료 시간 도래 - 서버 중지 프로세스 가동")
        result = await ncp_client.get_server_list()
        server_list = result.get("getServerInstanceListResponse", {}).get("serverInstanceList", [])

        if not server_list:
            logger.info("[Scheduler] 대상 서버 없음")
            return

        running_ids = [s["serverInstanceNo"] for s in server_list
                      if s["serverInstanceStatus"]["code"] == "RUN"]
        
        if running_ids:
            logger.info(f"[Scheduler] 서버 중지 요청: {running_ids}")
            await ncp_client.stop_server(running_ids)
        else:
            logger.info("[Scheduler] 중지할 서버가 없습니다 (이미 정지됨).")

    except Exception as e:
        logger.error(f"[Scheduler] 중지 프로세스 오류: {e}")


async def check_and_manage_servers():
    """수동 실행용: 현재 시간에 맞춰 상태 동기화"""
    try:
        if is_work_time():
            logger.info("[Manual] 현재 업무 시간입니다. 서버 시작을 시도합니다.")
            await auto_start_servers()
        else:
            logger.info("[Manual] 현재 업무 외 시간입니다. 서버 중지를 시도합니다.")
            await auto_stop_servers()
    except Exception as e:
        logger.error(f"[Manual] 오류 발생: {e}")


def start_scheduler():
    """스케줄러 시작 - 업무 시작/종료 시간에만 트리거"""
    # 업무 시작 시간 스케줄
    scheduler.add_job(
        auto_start_servers,
        'cron',
        hour=Config.WORK_START_HOUR,
        minute=Config.WORK_START_MINUTE,
        id='auto_start',
        replace_existing=True
    )
    
    # 업무 종료 시간 스케줄
    scheduler.add_job(
        auto_stop_servers,
        'cron',
        hour=Config.WORK_END_HOUR,
        minute=Config.WORK_END_MINUTE,
        id='auto_stop',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"[Scheduler] 스케줄러 시작됨 (시작: {Config.WORK_START_HOUR}:{Config.WORK_START_MINUTE:02d}, 종료: {Config.WORK_END_HOUR}:{Config.WORK_END_MINUTE:02d})")


def stop_scheduler():
    """스케줄러 중지"""
    scheduler.shutdown()
