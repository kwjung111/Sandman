# NCP 서버 관리 대시보드

네이버 클라우드 플랫폼(NCP) VServer를 설정된 업무 시간에 맞춰 자동으로 시작하고 중지하는 웹 대시보드입니다.

## 주요 기능

- **그룹별 스케줄링**: 그룹마다 업무 시작/종료 시간을 **시(Hour)와 분(Minute)** 단위로 설정, 서버를 그룹에 할당해 관리
- **주말 운영 정책**: 그룹별로 "업무 시간 적용" 또는 "주말 전체 중지" 선택 (전체 중지 시 토·일 매시 정각 자동 중지)
- **이름 기반 필터링**: `SERVER_NAME_FILTER`/`SERVER_NAME_EXCLUDE`로 관리 대상 서버 제한
- **동기화 기능**: 버튼 하나로 현재 시간 규칙에 맞춰 서버 상태 즉시 동기화
- **실시간 모니터링**: 서버 상태 변경 중 10초 간격 자동 새로고침, 규칙-실제 상태 불일치 표시

## CI/CD (GitHub Actions)

`main` 브랜치에 푸시하면 [.github/workflows/build-push.yml](.github/workflows/build-push.yml)이
이미지를 빌드해 레지스트리로 푸시합니다 (태그: git short SHA + `latest`).

저장소 Settings → Secrets and variables → Actions 에서 설정:

| 위치 | 이름 | 설명 |
|------|------|------|
| Variables | `HARBOR_REGISTRY` | 레지스트리 주소 (예: `harbor.example.com`) |
| Variables | `HARBOR_PROJECT` | 레지스트리 프로젝트명 (예: `tools`) |
| Variables | `IMAGE_NAME` | (선택) 이미지 이름, 기본 `ncp-server-manager` |
| Secrets | `HARBOR_ROBOT_USER` | 로봇 계정명 (push/pull 권한만 부여 권장) |
| Secrets | `HARBOR_ROBOT_SECRET` | 로봇 계정 시크릿 |

> 변수 미설정 시(포크 등) 푸시 없이 빌드 검증만 수행합니다.

## 서버 배포 (Linux)

```bash
# .env 파일에 이미지·인증키 준비 (권장 권한 600)
cp .env.example .env && chmod 600 .env && vi .env

chmod +x start.sh
./start.sh          # 기본 .env 사용, 다른 파일이면 ./start.sh /path/to/env
```

`start.sh`는 레지스트리 이미지면 자동으로 pull 후 기존 컨테이너를 교체하며,
SQLite 데이터는 호스트 `/data/ncp/data`(변경: `DATA_DIR`)에 저장되어 재배포에도 유지됩니다.

로컬에서 직접 빌드하려면: `docker build -t ncp-server-manager .`

## 환경 변수 설정 (.env 또는 Docker -e)

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `NCP_ACCESS_KEY` | (필수) | NCP API Access Key |
| `NCP_SECRET_KEY` | (필수) | NCP API Secret Key |
| `SERVER_NAME_FILTER` | "" | 포함할 서버 이름 (쉼표 구분) |
| `SERVER_NAME_EXCLUDE` | "" | 제외할 서버 이름 (쉼표 구분) |
| `NCP_API_URL` | (공공) | NCP API 엔드포인트 URL |
| `DB_PATH` | data/app.db | SQLite DB 파일 경로 |
| `IMAGE` | ncp-server-manager | (start.sh) 실행할 이미지 |
| `HOST_PORT` | 18081 | (start.sh) 호스트 포트 |
| `DATA_DIR` | /data/ncp/data | (start.sh) SQLite 저장 디렉토리 |

> 업무 시간·주말 포함 여부는 env가 아니라 **대시보드 설정 화면**에서 그룹별로 관리합니다 (SQLite 저장).
> 최초 실행 시 "기본 그룹"(09:00~18:00, 주말 제외)이 자동 생성됩니다.

## 스케줄링 동작

- **그룹 단위 관리**: 그룹에 할당된 서버만 자동 시작/중지 대상입니다. 미할당 서버는 자동 관리에서 제외됩니다.
- **자동 시작**: 그룹의 시작 시/분에 도달하면 해당 그룹의 정지된 서버를 시작합니다.
- **자동 중지**: 그룹의 종료 시/분에 도달하면 해당 그룹의 실행 중인 서버를 중지합니다. (설정에서 자동 중지를 끄면 건너뜀)
- **동기화(Sync)**: 사용자가 원할 때 언제든 현재 시간(업무 중/퇴근)에 맞춰 상태를 맞춥니다.
- **수동 조작 존중**: 정해진 트리거 시간 외에는 사용자가 수동으로 켜거나 끈 상태가 유지됩니다.

## 기술 스택

- **Backend**: Python, FastAPI, APScheduler, httpx
- **Frontend**: HTML5, Modern CSS (Vanilla JS)
- **Deployment**: Docker (Linux/Windows)
