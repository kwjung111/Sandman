#!/bin/bash
# 사용법: ./start.sh [env파일경로]   (기본: .env)
#
# env 파일 예시 (권장 권한: chmod 600):
#   # --- 컨테이너 설정 (스크립트가 읽음) ---
#   IMAGE=<your-registry>/<project>/ncp-server-manager:latest
#   HOST_PORT=18081
#   DATA_DIR=/data/ncp/data    # SQLite 저장 위치 (기본값, 바꿀 때만 지정)
#   # --- 앱 설정 (컨테이너로 전달됨) ---
#   NCP_ACCESS_KEY=...
#   NCP_SECRET_KEY=...
#   NCP_API_URL=https://ncloud.apigw.gov-ntruss.com
#   SERVER_NAME_FILTER=dev
#   SERVER_NAME_EXCLUDE=prod,backup
#
# * 업무시간/주말(WORK_*, INCLUDE_WEEKENDS)은 더 이상 env로 받지 않음 —
#   웹 UI의 설정 화면에서 그룹별로 관리 (SQLite 볼륨에 저장)
# * 키를 CLI 인자로 받지 않는 이유: 셸 히스토리와 ps 출력에 평문 노출되기 때문

set -euo pipefail

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "환경 파일이 없습니다: $ENV_FILE"
    echo "NCP_ACCESS_KEY, NCP_SECRET_KEY 를 포함한 env 파일을 만든 뒤 다시 실행하세요."
    echo "  cp .env.example .env && chmod 600 .env && vi .env"
    exit 1
fi

# env 파일에서 IMAGE/HOST_PORT/DATA_DIR 로드 (셸 환경변수가 있으면 그쪽 우선)
set -a; . "$ENV_FILE"; set +a
IMAGE="${IMAGE:-ncp-server-manager}"
HOST_PORT="${HOST_PORT:-18081}"

# SQLite 저장 위치 (호스트 디렉토리 바인드)
DATA_DIR="${DATA_DIR:-/data/ncp/data}"
mkdir -p "$DATA_DIR"

# 레지스트리 이미지면 최신본 pull
case "$IMAGE" in
    */*) docker pull "$IMAGE" ;;
esac

# 기존 컨테이너 교체
docker rm -f ncp-manager 2>/dev/null || true

docker run -d \
   --name ncp-manager \
   --restart unless-stopped \
   -p "$HOST_PORT":8000 \
   -v "$DATA_DIR":/app/data \
   --env-file "$ENV_FILE" \
   "$IMAGE"

echo "[OK] ncp-manager 실행됨 → http://localhost:$HOST_PORT (이미지: $IMAGE)"
