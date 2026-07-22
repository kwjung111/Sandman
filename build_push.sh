#!/bin/bash
# NCP Server Manager - Docker 빌드 & Harbor 푸시 (Linux/macOS)
#
# 사용법:
#   ./build_push.sh              # build.env 설정으로 빌드 + 푸시
#   ./build_push.sh --no-push    # 빌드만
#   TAG=v1.2.0 ./build_push.sh   # 태그 지정
#
# 설정 우선순위: 환경변수 > build.env 파일
# 레지스트리 로그인은 미리 한 번 해두세요:  docker login <registry>
set -euo pipefail
cd "$(dirname "$0")"

NO_PUSH=false
[ "${1:-}" = "--no-push" ] && NO_PUSH=true

# 1. build.env 로드 (이미 설정된 환경변수는 유지)
if [ -f build.env ]; then
    while IFS='=' read -r key val; do
        case "$key" in ''|\#*) continue ;; esac
        key=$(echo "$key" | tr -d ' ')
        val=$(echo "$val" | tr -d ' \r')
        [ -n "$val" ] && [ -z "${!key:-}" ] && export "$key=$val"
    done < build.env
fi

# 2. 필수 값 검증
if [ -z "${REGISTRY:-}" ]; then
    echo "[ERROR] REGISTRY 가 설정되지 않았습니다."
    echo "  cp build.env.example build.env  후 값을 채우거나 REGISTRY=... 로 지정하세요."
    exit 1
fi
PROJECT="${REGISTRY_PROJECT:-library}"
IMAGE_NAME="${IMAGE_NAME:-ncp-server-manager}"

# 3. 태그: TAG env > IMAGE_TAG(build.env) > git short hash > latest
#    커밋 안 된 변경이 있으면 -dirty 접미사
TAG="${TAG:-${IMAGE_TAG:-}}"
if [ -z "$TAG" ]; then
    TAG=$(git rev-parse --short HEAD 2>/dev/null || echo latest)
    if [ "$TAG" != "latest" ] && ! git diff --quiet HEAD 2>/dev/null; then
        TAG="$TAG-dirty"
    fi
fi

FULL_IMAGE="$REGISTRY/$PROJECT/$IMAGE_NAME:$TAG"
LATEST_IMAGE="$REGISTRY/$PROJECT/$IMAGE_NAME:latest"

echo "=============================================="
echo " 이미지: $FULL_IMAGE"
echo " 푸시:   $([ "$NO_PUSH" = true ] && echo '안 함 (빌드만)' || echo "$REGISTRY")"
echo "=============================================="

# 4. 빌드
docker build -t "$FULL_IMAGE" -t "$LATEST_IMAGE" .
echo "[OK] 빌드 완료"

[ "$NO_PUSH" = true ] && exit 0

# 5. 푸시
docker push "$FULL_IMAGE"
docker push "$LATEST_IMAGE"

echo "=============================================="
echo "[SUCCESS] 푸시 완료:"
echo "  $FULL_IMAGE"
echo "  $LATEST_IMAGE"
echo "=============================================="
