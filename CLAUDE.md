# CLAUDE.md

이 파일은 Claude Code가 이 프로젝트를 이해하는 데 필요한 컨텍스트를 제공합니다.

## 프로젝트 개요

NCP(네이버 클라우드 플랫폼) VServer를 업무 시간 기반으로 자동 관리하는 웹 대시보드입니다. 비용 절감을 위해 업무 외 시간에 서버를 자동으로 중지합니다.

## 핵심 로직

### 이름 기반 필터링
- `Config.SERVER_NAME_FILTER`와 `Config.SERVER_NAME_EXCLUDE`를 사용하여 서버 필터링
- `app/ncp_client.py`의 `get_server_list()`에서 클라이언트 사이드 필터링 수행

### 스케줄러 (Trigger-based)
- APScheduler의 `cron` 방식을 사용하여 특정 시간에만 트리거
- 시작: `Config.WORK_START_HOUR:Config.WORK_START_MINUTE`
- 종료: `Config.WORK_END_HOUR:Config.WORK_END_MINUTE`
- `auto_start_servers()`, `auto_stop_servers()` 함수가 각각 담당

### 대시보드 UI (State Management)
- 서버 상태가 `pending`(작업 중)인 경우 10초 간격으로 자동 폴링
- 모든 서버가 안정 상태(`RUN`, `STOP`)이면 폴링 중단
- "동기화" 버튼은 현재 시간 규칙을 즉시 강제 적용 (`/api/scheduler/run`)

## 주요 파일 및 도구

| 파일 | 역할 |
|------|------|
| `app/scheduler.py` | 트리거 기반 자동 시작/중지 로직 및 수동 동기화 |
| `build_release.bat` | (Windows) Docker 빌드 및 이미지 Export (.tar) |
| `start.sh` | (Linux) Docker 컨테이너 실행 (인증키 주입) |
| `Dockerfile` | Python 3.11-slim 기반 멀티 스테이지 빌드 지향 이미지 |

## 배포 아티팩트

- `ncp-server-manager.tar`: 도커 이미지 아카이브
- `start.sh`: 실행 스크립트 (서버 배포용)
- `.env.local`: 로컬 오버라이드 설정 (Git 제외)

## 서버 상태 코드

| 코드 | 의미 |
|------|------|
| `RUN` | 실행 중 |
| `NSTOP` | 정지됨 |
| `STOP` | 정지됨 |
| `INIT` | 초기화 중 |
| `CREAT` | 생성 중 |
| `STRT` | 시작 중 |

## 개발 시 주의사항

- NCP API는 비동기(async/await)로 호출
- 서버 시작/중지 후 상태 반영까지 시간 소요 (프론트에서 2초 딜레이 후 새로고침)
- Cloud DB(MySQL, PostgreSQL, Redis)는 시작/중지 API 미지원으로 제외됨

## 실행 명령어

```bash
# 개발 서버
uvicorn app.main:app --reload

# 프로덕션
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
