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

PAGE_SIZE = 100


class NCPApiError(Exception):
    """NCP API 호출 실패 (연결 오류, 비200 응답, 오류 응답 본문)"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


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
        return base64.b64encode(signature).decode("utf-8")

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

    async def _request(self, client: httpx.AsyncClient, method: str, uri_with_params: str,
                       response_key: str, action_desc: str) -> dict:
        """공통 요청 처리: 실패 시 NCPApiError 발생, 성공 시 response_key의 값 반환"""
        url = f"{self.base_url}{uri_with_params}"
        try:
            if method == "GET":
                response = await client.get(url, headers=self._get_headers("GET", uri_with_params))
            else:
                response = await client.post(url, headers=self._get_headers("POST", uri_with_params))
        except httpx.HTTPError as e:
            logger.error(f"[API] {action_desc} 연결 실패: {e}")
            raise NCPApiError(f"{action_desc} 연결 실패: {e}") from e

        if response.status_code != 200:
            logger.error(f"[API] {action_desc} HTTP {response.status_code}: {response.text[:300]}")
            raise NCPApiError(
                f"{action_desc} 실패 (HTTP {response.status_code}): {response.text[:300]}",
                response.status_code,
            )

        result = response.json()
        if response_key not in result:
            error_msg = result.get("responseError", {}).get("returnMessage", "Unknown error")
            logger.error(f"[API] {action_desc} 오류 응답: {error_msg}")
            raise NCPApiError(f"{action_desc} 실패: {error_msg}")

        return result[response_key]

    async def get_server_list(self) -> dict:
        """서버 인스턴스 목록 조회 (페이징 처리 + 이름 필터링). 실패 시 NCPApiError"""
        all_servers: list[dict] = []
        page_no = 1

        async with httpx.AsyncClient() as client:
            while True:
                uri = (f"/vserver/v2/getServerInstanceList?responseFormatType=json"
                       f"&pageNo={page_no}&pageSize={PAGE_SIZE}")
                logger.info(f"[API] GET {uri}")
                resp = await self._request(client, "GET", uri,
                                           "getServerInstanceListResponse", "서버 목록 조회")
                page = resp.get("serverInstanceList", [])
                all_servers.extend(page)

                total_rows = resp.get("totalRows")
                if len(page) < PAGE_SIZE or (total_rows is not None and len(all_servers) >= total_rows):
                    break
                page_no += 1

        # 서버 이름 필터링
        name_filters = [f.strip().lower() for f in Config.SERVER_NAME_FILTER.split(",") if f.strip()]
        name_excludes = [f.strip().lower() for f in Config.SERVER_NAME_EXCLUDE.split(",") if f.strip()]

        filtered = all_servers
        if name_filters:
            filtered = [s for s in filtered if any(f in s.get("serverName", "").lower() for f in name_filters)]
        if name_excludes:
            filtered = [s for s in filtered if not any(e in s.get("serverName", "").lower() for e in name_excludes)]

        logger.info(f"[API] 필터 결과: {len(all_servers)}개 중 {len(filtered)}개 "
                    f"(포함: {name_filters or '전체'}, 제외: {name_excludes or '없음'})")

        return {"getServerInstanceListResponse": {"serverInstanceList": filtered,
                                                  "totalRows": len(filtered)}}

    async def stop_server(self, server_instance_nos: list[str]) -> dict:
        """서버 인스턴스 중지. 실패 시 NCPApiError"""
        params = "&".join([f"serverInstanceNoList.{i+1}={no}" for i, no in enumerate(server_instance_nos)])
        uri = f"/vserver/v2/stopServerInstances?responseFormatType=json&{params}"

        logger.info(f"[API] POST - 중지 요청: {server_instance_nos}")
        async with httpx.AsyncClient() as client:
            resp = await self._request(client, "POST", uri,
                                       "stopServerInstancesResponse", "서버 중지")
        logger.info(f"[API] 서버 중지 성공: {server_instance_nos}")
        return {"stopServerInstancesResponse": resp}

    async def start_server(self, server_instance_nos: list[str]) -> dict:
        """서버 인스턴스 시작. 실패 시 NCPApiError"""
        params = "&".join([f"serverInstanceNoList.{i+1}={no}" for i, no in enumerate(server_instance_nos)])
        uri = f"/vserver/v2/startServerInstances?responseFormatType=json&{params}"

        logger.info(f"[API] POST - 시작 요청: {server_instance_nos}")
        async with httpx.AsyncClient() as client:
            resp = await self._request(client, "POST", uri,
                                       "startServerInstancesResponse", "서버 시작")
        logger.info(f"[API] 서버 시작 성공: {server_instance_nos}")
        return {"startServerInstancesResponse": resp}


ncp_client = NCPClient()
