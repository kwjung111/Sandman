# CLAUDE.md

이 파일은 Claude Code가 이 프로젝트를 이해하는 데 필요한 컨텍스트를 제공합니다.

## 프로젝트 개요

NCP(네이버 클라우드 플랫폼) VServer를 업무 시간 기반으로 자동 관리하는 웹 대시보드입니다. 비용 절감을 위해 업무 외 시간에 서버를 자동으로 중지합니다.

## 핵심 로직

### 이름 기반 필터링
- `Config.SERVER_NAME_FILTER`와 `Config.SERVER_NAME_EXCLUDE`를 사용하여 서버 필터링
- `app/ncp_client.py`의 `get_server_list()`에서 클라이언트 사이드 필터링 수행

### 그룹 기반 관리 (SQLite)
- `app/database.py` — SQLite(`data/app.db`, `DB_PATH` env로 변경 가능)에 그룹/할당 저장
  - `groups`: 그룹별 업무 시작·종료 시간, 주말 운영 정책
    (`include_weekends` 컬럼: 1=주말에도 업무시간 적용, 0=**주말 전체 중지** — 스키마 변경 없이 의미 재정의)
  - `server_groups`: 서버 instanceNo → 그룹 할당 (그룹 삭제 시 CASCADE로 할당 해제)
- **그룹에 할당된 서버만 자동 시작/중지 대상.** 미할당 서버는 목록에 보이지만 자동 관리 제외
- 최초 실행 시 그룹이 없으면 "기본 그룹"(09:00~18:00, 주말 제외) 시드. 업무시간 관련 env 없음
- 도커 배포 시 `/app/data`에 볼륨 마운트 필수 (매니페스트 compose가 named volume으로 처리. 없으면 재배포 시 그룹 설정 유실)

### 스케줄러 (Trigger-based, 그룹별)
- APScheduler `cron` 방식, **그룹마다** 시작/종료 잡 등록 (`group_{id}_start`/`group_{id}_stop`)
- 그룹 생성/수정/삭제 시 `reschedule_jobs()`로 전체 재등록
- `auto_start_group(group_id)`, `auto_stop_group(group_id)`이 해당 그룹 할당 서버만 처리
- **NCP API 실패 시 5분 간격 최대 3회 재시도** (`NCPApiError` → date 잡 등록)
- `misfire_grace_time=600` — 재시작·지연으로 트리거를 놓쳐도 10분 안이면 실행
- **자동 중지는 주말에도 수행** (주말에 수동 기동한 서버도 종료 시각에 꺼짐)
- **주말 스위프** (`weekend_sweep` 잡): 토·일 매시 정각, '주말 전체 중지' 그룹의 실행 중 서버를 중지.
  수동으로 켜도 다음 정각에 다시 꺼짐 — 주말 작업 필요 시 자동 중지 토글을 끄는 게 공식 우회로
- 그룹 시간 검증(시작 < 종료, 자정 넘김 불가)은 백엔드 Pydantic에서 강제
- 수동 동기화(`/api/scheduler/run`)는 `{started, stopped, stop_skipped, errors}` 요약 반환

### NCP 클라이언트 (`app/ncp_client.py`)
- 실패 시 오류 dict가 아닌 **`NCPApiError` 예외** 발생 (연결 실패/비200/오류 응답 모두)
- 서버 목록은 `pageNo`/`pageSize=100` 페이징 루프로 전체 수집
- API 라우터는 `NCPApiError`를 HTTP 502로 변환

### 자동 중지 토글 (settings 테이블)
- `settings` 테이블의 `auto_stop_enabled` 키 (기본 켜짐), `GET/PUT /api/settings`
- 꺼져 있으면 그룹 업무 종료 cron·수동 동기화 모두 **중지를 건너뜀** (자동 시작은 계속 동작)

### UI 구조 (2페이지)
- `/` (`static/index.html`) — **읽기 전용 대시보드.** 그룹·서버 현황 조회 + 수동 시작/중지/동기화만 가능
- `/settings` (`static/settings.html`) — 모든 설정 변경: 자동 중지 토글, 그룹 CRUD, 서버 그룹 할당
- 공통 스타일은 `static/style.css`
- 서버 상태가 `pending`(작업 중)인 경우 10초 간격으로 자동 폴링, 안정 상태(`RUN`, `STOP`)면 중단
- "동기화" 버튼은 현재 시간 규칙을 즉시 강제 적용 (`/api/scheduler/run`)

## 주요 파일 및 도구

| 파일 | 역할 |
|------|------|
| `app/database.py` | SQLite 그룹/서버 할당 저장소 |
| `app/scheduler.py` | 그룹별 트리거 기반 자동 시작/중지 로직 및 수동 동기화 |
| `.github/workflows/build-push.yml` | CI/CD — main 푸시 시 ① 이미지 빌드 & 레지스트리 푸시 ② 매니페스트 저장소(`vars.MANIFEST_REPO`)의 compose 태그를 새 SHA로 커밋. 설정은 repo Variables/Secrets (저장소에 하드코딩 금지) |
| `Dockerfile` | Python 3.11-slim 기반 멀티 스테이지 빌드 지향 이미지 |

## 배포

- CI/CD: main 푸시 → GitHub Actions가 빌드·레지스트리 푸시 → 매니페스트 저장소에 태그 커밋 → 배포 도구(Portainer)가 git 폴링으로 재배포
- **롤백은 이 저장소에서 `git revert`** (매니페스트만 되돌리면 다음 푸시가 덮어씀)
- `.env.local`: 로컬 개발용 오버라이드 설정 (Git 제외)

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
