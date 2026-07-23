# NCP 서버 관리 대시보드

NCP VServer를 그룹별 업무시간에 맞춰 자동 시작/중지하는 웹 대시보드.

- 그룹마다 업무 시작/종료 시각·주말 정책("업무시간 적용" / "주말 전체 중지") 설정, 서버를 그룹에 할당해 관리
- 그룹 미할당 서버는 자동 관리 제외. 설정에서 자동 중지 전체를 끌 수 있음
- 이름 필터: `SERVER_NAME_FILTER` / `SERVER_NAME_EXCLUDE`

## 환경 변수 (컨테이너에 주입)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NCP_ACCESS_KEY` / `NCP_SECRET_KEY` | (필수) | NCP API 키 |
| `NCP_API_URL` | (공공) | API 엔드포인트 |
| `SERVER_NAME_FILTER` / `SERVER_NAME_EXCLUDE` | "" | 관리 대상 이름 필터 (쉼표 구분) |
| `DB_PATH` | data/app.db | SQLite 경로. 영속화하려면 `/app/data`에 볼륨 마운트 |

업무시간·그룹은 env가 아니라 대시보드 설정 화면에서 관리(SQLite 저장). 최초 실행 시 기본 그룹(09:00~18:00, 주말 제외) 자동 생성.

## 배포 (CI/CD)

`main` 푸시 → GitHub Actions가 이미지 빌드·레지스트리 푸시 → 매니페스트 저장소 태그 커밋 → 배포 도구 폴링 재배포.
**롤백은 이 저장소에서 `git revert` 후 푸시** (매니페스트만 되돌리면 다음 푸시가 덮어씀).

필요한 repo Variables/Secrets: `HARBOR_REGISTRY`·`HARBOR_PROJECT`·`MANIFEST_REPO` (+ 선택 `IMAGE_NAME`·`MANIFEST_PATH`), `HARBOR_ROBOT_USER`·`HARBOR_ROBOT_SECRET`·`MANIFEST_REPO_TOKEN`. 미설정 시 빌드 검증만 수행.
