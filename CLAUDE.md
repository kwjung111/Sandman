# CLAUDE.md

NCP VServer를 그룹별 업무시간에 맞춰 자동 시작/중지하는 FastAPI 웹 대시보드. 비용 절감이 목적.

## 핵심 로직 (비자명한 것만)

**이름 필터** — `Config.SERVER_NAME_FILTER`/`SERVER_NAME_EXCLUDE`, `app/ncp_client.py` `get_server_list()`에서 클라이언트 사이드 필터링.

**그룹 관리 (SQLite, `app/database.py`)** — `DB_PATH` 기본 `data/app.db`.
- `groups`: 그룹별 시작·종료 시각 + `include_weekends`(1=주말도 업무시간 적용, 0=주말 전체 중지 — 스키마 변경 없이 의미 재정의)
- `server_groups`: instanceNo → 그룹 (그룹 삭제 시 CASCADE)
- **그룹 할당 서버만 자동 관리.** 미할당은 목록에 보이나 제외
- 그룹 없으면 기본 그룹(09:00~18:00, 주말 제외) 시드. 업무시간 env 없음
- 도커 배포 시 `/app/data` 볼륨 필수 (없으면 재배포마다 설정 유실)

**스케줄러 (`app/scheduler.py`, APScheduler cron, 그룹별)**
- 그룹마다 `group_{id}_start`/`_stop` 잡, 그룹 변경 시 `reschedule_jobs()`로 전체 재등록
- NCP API 실패 시 5분 간격 최대 3회 재시도(date 잡), `misfire_grace_time=600`
- 자동 중지는 주말에도 수행. `weekend_sweep` 잡: 토·일 매시 정각 '주말 전체 중지' 그룹 실행 서버 중지 (수동 기동해도 다시 꺼짐 — 우회는 자동 중지 토글 OFF)
- 그룹 시간 검증(시작<종료, 자정 넘김 불가)은 Pydantic에서 강제
- `/api/scheduler/run` = 수동 동기화, `{started, stopped, stop_skipped, errors}` 반환

**NCP 클라이언트** — 실패 시 `NCPApiError` 예외(연결/비200/오류 응답 전부), 라우터가 502로 변환. 목록은 `pageSize=100` 페이징.

**자동 중지 토글** — `settings.auto_stop_enabled`(기본 켜짐), `GET/PUT /api/settings`. 끄면 종료 cron·수동 동기화의 중지만 건너뜀(시작은 동작).

**UI 2페이지** — `/`(index.html) 읽기 전용 대시보드, `/settings`(settings.html) 설정 변경. `pending` 상태면 10초 폴링, 안정되면 중단.

## 배포

`main` 푸시 → GitHub Actions(빌드·레지스트리 푸시 → 매니페스트 태그 커밋) → Portainer 폴링 재배포. 설정은 repo Variables/Secrets(하드코딩 금지). 롤백은 이 저장소에서 `git revert`. `.env.local`은 로컬 오버라이드(Git 제외).

## 참고

- 서버 상태 코드: `RUN` 실행 / `NSTOP`·`STOP` 정지 / `INIT`·`CREAT` 초기화·생성 / `STRT` 시작 중
- NCP API는 async 호출, 시작/중지 후 상태 반영에 지연 있음
- Cloud DB(MySQL/PostgreSQL/Redis)는 시작/중지 API 미지원이라 제외
