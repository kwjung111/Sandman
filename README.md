# NCP 서버 관리 대시보드

네이버 클라우드 플랫폼(NCP) VServer를 설정된 업무 시간에 맞춰 자동으로 시작하고 중지하는 웹 대시보드입니다.

## 주요 기능

- **정밀한 스케줄링**: 업무 시작/종료 시간을 **시(Hour)와 분(Minute)** 단위로 설정 가능
- **이름 기반 필터링**: `SERVER_NAME_FILTER`를 통해 특정 서버만 관리 (또는 제외)
- **동기화 기능**: 버튼 하나로 현재 시간 규칙에 맞춰 서버 상태 즉시 동기화
- **실시간 모니터링**: 10초 간격 자동 새로고침(상태 변경 시) 및 커스텀 툴팁 제공
- **보안 강화**: 서버에 `.env` 파일 없이 실행 인자로 인증키 전달 가능 (Docker)

## 설치 및 배포

### 1. 로컬 빌드 (Windows)
프로젝트 폴더에서 `build_release.bat`를 실행하여 도커 이미지와 배포용 파일을 생성합니다.
- 결과물: `ncp-server-manager.tar`

### 2. 서버 배포 (Linux)
생성된 `.tar` 파일과 `start.sh` 스크립트를 서버로 복사한 후 실행합니다.

```bash
# 이미지 로드
docker load -i ncp-server-manager.tar

# 컨테이너 실행 (인자로 인증키 전달)
chmod +x start.sh
./start.sh "YOUR_ACCESS_KEY" "YOUR_SECRET_KEY"
```

## 환경 변수 설정 (.env 또는 Docker -e)

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `NCP_ACCESS_KEY` | (필수) | NCP API Access Key |
| `NCP_SECRET_KEY` | (필수) | NCP API Secret Key |
| `WORK_START_HOUR` | 9 | 업무 시작 시간 (시) |
| `WORK_START_MINUTE` | 0 | 업무 시작 시간 (분) |
| `WORK_END_HOUR` | 18 | 업무 종료 시간 (시) |
| `WORK_END_MINUTE` | 0 | 업무 종료 시간 (분) |
| `SERVER_NAME_FILTER` | "" | 포함할 서버 이름 (쉼표 구분) |
| `SERVER_NAME_EXCLUDE` | "" | 제외할 서버 이름 (쉼표 구분) |
| `INCLUDE_WEEKENDS` | false | 주말 자동화 포함 여부 |
| `NCP_API_URL` | (공공) | NCP API 엔드포인트 URL |

## 스케줄링 동작

- **자동 시작**: 설정된 시작 시/분에 도달하면 정지된 대상 서버를 모두 시작합니다.
- **자동 중지**: 설정된 종료 시/분에 도달하면 실행 중인 대상 서버를 모두 중지합니다.
- **동기화(Sync)**: 사용자가 원할 때 언제든 현재 시간(업무 중/퇴근)에 맞춰 상태를 맞춥니다.
- **수동 조작 존중**: 정해진 트리거 시간 외에는 사용자가 수동으로 켜거나 끈 상태가 유지됩니다.

## 기술 스택

- **Backend**: Python, FastAPI, APScheduler, httpx
- **Frontend**: HTML5, Modern CSS (Vanilla JS)
- **Deployment**: Docker (Linux/Windows)
