import hashlib
import hmac
import base64
import time
import logging
import httpx
from .config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class NCPClient:
    """네이버 클라우드 플랫폼 API 클라이언트"""

    def __init__(self):
        self.access_key = Config.NCP_ACCESS_KEY
        self.secret_key = Config.NCP_SECRET_KEY
        self.base_url = Config.NCP_API_URL

        # 디버그: API 키 로드 확인
        if self.access_key:
            logger.info(f"[Config] Access Key 로드됨: {self.access_key[:8]}...{self.access_key[-4:]}")
        else:
            logger.error("[Config] Access Key가 설정되지 않았습니다!")

        if self.secret_key:
            logger.info(f"[Config] Secret Key 로드됨: {self.secret_key[:8]}...{self.secret_key[-4:]}")
        else:
            logger.error("[Config] Secret Key가 설정되지 않았습니다!")

        logger.info(f"[Config] API URL: {self.base_url}")

    def _make_signature(self, method: str, uri: str, timestamp: str) -> str:
        """API 요청 서명 생성"""
        message = f"{method} {uri}\n{timestamp}\n{self.access_key}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
        sig_str = base64.b64encode(signature).decode("utf-8")

        # 디버그
        logger.debug(f"[Signature] Message: {repr(message)}")
        logger.debug(f"[Signature] Result: {sig_str[:20]}...")

        return sig_str

    def _get_headers(self, method: str, url_with_params: str) -> dict:
        """API 요청 헤더 생성 (url_with_params는 query string 포함)"""
        timestamp = str(int(time.time() * 1000))
        signature = self._make_signature(method, url_with_params, timestamp)

        return {
            "x-ncp-apigw-timestamp": timestamp,
            "x-ncp-iam-access-key": self.access_key,
            "x-ncp-apigw-signature-v2": signature,
            "Content-Type": "application/json"
        }

    async def get_server_list(self) -> dict:
        """서버 인스턴스 목록 조회 (이름 필터링)"""
        uri_with_params = "/vserver/v2/getServerInstanceList?responseFormatType=json"
        url = f"{self.base_url}{uri_with_params}"

        logger.info(f"[API] GET {uri_with_params}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers("GET", uri_with_params)
            )

            if response.status_code != 200:
                logger.error(f"[API] HTTP {response.status_code}: {response.text}")
                return {"error": response.text, "status_code": response.status_code}

            result = response.json()

            if "getServerInstanceListResponse" in result:
                server_list = result["getServerInstanceListResponse"].get("serverInstanceList", [])

                # 서버 이름 필터링
                name_filters = [f.strip().lower() for f in Config.SERVER_NAME_FILTER.split(",") if f.strip()]
                name_excludes = [f.strip().lower() for f in Config.SERVER_NAME_EXCLUDE.split(",") if f.strip()]

                filtered = server_list

                # 포함 필터 적용
                if name_filters:
                    filtered = [s for s in filtered if any(f in s.get("serverName", "").lower() for f in name_filters)]

                # 제외 필터 적용
                if name_excludes:
                    filtered = [s for s in filtered if not any(e in s.get("serverName", "").lower() for e in name_excludes)]

                result["getServerInstanceListResponse"]["serverInstanceList"] = filtered
                logger.info(f"[API] 필터 결과: {len(server_list)}개 중 {len(filtered)}개 (포함: {name_filters or '전체'}, 제외: {name_excludes or '없음'})")
            else:
                error_msg = result.get("responseError", {}).get("returnMessage", "Unknown error")
                logger.error(f"[API] 서버 목록 조회 실패: {error_msg}")

            return result

    async def stop_server(self, server_instance_nos: list[str]) -> dict:
        """서버 인스턴스 중지"""
        params = "&".join([f"serverInstanceNoList.{i+1}={no}" for i, no in enumerate(server_instance_nos)])
        uri_with_params = f"/vserver/v2/stopServerInstances?responseFormatType=json&{params}"
        url = f"{self.base_url}{uri_with_params}"

        logger.info(f"[API] POST - 중지 요청: {server_instance_nos}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._get_headers("POST", uri_with_params)
            )

            if response.status_code != 200:
                logger.error(f"[API] HTTP {response.status_code}: {response.text}")
                return {"error": response.text, "status_code": response.status_code}

            result = response.json()

            if "stopServerInstancesResponse" in result:
                logger.info(f"[API] 서버 중지 성공: {server_instance_nos}")
            else:
                error_msg = result.get("responseError", {}).get("returnMessage", "Unknown error")
                logger.error(f"[API] 서버 중지 실패: {error_msg}")

            return result

    async def start_server(self, server_instance_nos: list[str]) -> dict:
        """서버 인스턴스 시작"""
        params = "&".join([f"serverInstanceNoList.{i+1}={no}" for i, no in enumerate(server_instance_nos)])
        uri_with_params = f"/vserver/v2/startServerInstances?responseFormatType=json&{params}"
        url = f"{self.base_url}{uri_with_params}"

        logger.info(f"[API] POST - 시작 요청: {server_instance_nos}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._get_headers("POST", uri_with_params)
            )

            if response.status_code != 200:
                logger.error(f"[API] HTTP {response.status_code}: {response.text}")
                return {"error": response.text, "status_code": response.status_code}

            result = response.json()

            if "startServerInstancesResponse" in result:
                logger.info(f"[API] 서버 시작 성공: {server_instance_nos}")
            else:
                error_msg = result.get("responseError", {}).get("returnMessage", "Unknown error")
                logger.error(f"[API] 서버 시작 실패: {error_msg}")

            return result


ncp_client = NCPClient()
