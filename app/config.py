import os
import logging
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Config")

# 1. .env.local 로드 (로컬 오버라이드용, 존재하면)
load_dotenv(".env.local")

# 2. .env 로드 (기본 설정, 시스템 환경변수나 .env.local이 있으면 덮어쓰지 않음)
load_dotenv(".env")


class Config:
    NCP_ACCESS_KEY = os.getenv("NCP_ACCESS_KEY", "")
    NCP_SECRET_KEY = os.getenv("NCP_SECRET_KEY", "")

    WORK_START_HOUR = int(os.getenv("WORK_START_HOUR", "9"))
    WORK_START_MINUTE = int(os.getenv("WORK_START_MINUTE", "0"))
    
    WORK_END_HOUR = int(os.getenv("WORK_END_HOUR", "18"))
    WORK_END_MINUTE = int(os.getenv("WORK_END_MINUTE", "0"))
    
    INCLUDE_WEEKENDS = os.getenv("INCLUDE_WEEKENDS", "false").lower() == "true"

    # 서버 이름 필터 - 포함 (쉼표로 구분)
    SERVER_NAME_FILTER = os.getenv("SERVER_NAME_FILTER", "")

    # 서버 이름 필터 - 제외 (쉼표로 구분)
    SERVER_NAME_EXCLUDE = os.getenv("SERVER_NAME_EXCLUDE", "")

    # 일반: ncloud.apigw.ntruss.com / 정부: ncloud.apigw.gov-ntruss.com
    NCP_API_URL = os.getenv("NCP_API_URL", "https://ncloud.apigw.gov-ntruss.com")

    @classmethod
    def log_config(cls):
        """현재 적용된 설정 출력 (민감정보 마스킹)"""
        ak_masked = f"{cls.NCP_ACCESS_KEY[:4]}****{cls.NCP_ACCESS_KEY[-4:]}" if cls.NCP_ACCESS_KEY else "Not Set"
        sk_masked = f"{cls.NCP_SECRET_KEY[:4]}****{cls.NCP_SECRET_KEY[-4:]}" if cls.NCP_SECRET_KEY else "Not Set"
        
        logger.info("========== 설정 로드 완료 ==========")
        logger.info(f"API URL: {cls.NCP_API_URL}")
        logger.info(f"Access Key: {ak_masked}")
        logger.info(f"Secret Key: {sk_masked}")
        logger.info(f"업무 시간: {cls.WORK_START_HOUR:02d}:{cls.WORK_START_MINUTE:02d} ~ {cls.WORK_END_HOUR:02d}:{cls.WORK_END_MINUTE:02d}")
        logger.info(f"주말 포함: {cls.INCLUDE_WEEKENDS}")
        logger.info(f"이름 필터(포함): {cls.SERVER_NAME_FILTER or '(전체)'}")
        logger.info(f"이름 필터(제외): {cls.SERVER_NAME_EXCLUDE or '(없음)'}")
        logger.info("====================================")

# 앱 시작 시 설정 로그 출력
Config.log_config()
