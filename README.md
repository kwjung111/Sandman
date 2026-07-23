# NCP 서버 관리 대시보드

네이버 클라우드 플랫폼(NCP) VServer를 설정된 업무 시간에 맞춰 자동으로 시작하고 중지하는 웹 대시보드입니다.

## 주요 기능

- **그룹별 스케줄링**: 그룹마다 업무 시작/종료 시간을 **시(Hour)와 분(Minute)** 단위로 설정, 서버를 그룹에 할당해 관리
- **주말 운영 정책**: 그룹별로 "업무 시간 적용" 또는 "주말 전체 중지" 선택 (전체 중지 시 토·일 매시 정각 자동 중지)
- **이름 기반 필터링**: `SERVER_NAME_FILTER`/`SERVER_NAME_EXCLUDE`로 관리 대상 서버 제한
- **동기화 기능**: 버튼 하나로 현재 시간 규칙에 맞춰 서버 상태 즉시 동기화
- **실시간 모니터링**: 서버 상태 변경 중 10초 간격 자동 새로고침, 규칙-실제 상태 불일치 표시

## CI/CD (GitHub Actions + GitOps)

`main` 브랜치에 푸시하면 [.github/workflows/build-push.yml](.github/workflows/build-push.yml)이:

1. **build** — 이미지를 빌드해 레지스트리로 푸시 (태그: git short SHA + `latest`)
2. **update-manifest** — 매니페스트 저장소의 compose 이미지 태그를 새 SHA로 교체하는 커밋을 푸시
   → 배포 도구(Portainer 등)가 매니페스트 저장소를 폴링해 재배포

```
git push (main)
  → CI: 빌드 → 레지스트리 푸시 (:<sha> + :latest)
  → CI: 매니페스트 저장소에 "deploy: <sha>" 커밋
  → 배포 도구가 git 폴링 → 재배포
```

저장소 Settings → Secrets and variables → Actions 에서 설정:

| 위치 | 이름 | 설명 |
|------|------|------|
| Variables | `HARBOR_REGISTRY` | 레지스트리 주소 (예: `harbor.example.com`) |
| Variables | `HARBOR_PROJECT` | 레지스트리 프로젝트명 (예: `tools`) |
| Variables | `IMAGE_NAME` | (선택) 이미지 이름, 기본 `ncp-server-manager` |
| Variables | `MANIFEST_REPO` | 매니페스트 저장소 (예: `org/manifest-repo`) — 미설정 시 매니페스트 갱신 생략 |
| Variables | `MANIFEST_PATH` | (선택) compose 파일 경로, 기본 `ncp-manager/docker-compose.yml` |
| Secrets | `HARBOR_ROBOT_USER` | 로봇 계정명 (push/pull 권한만 부여 권장) |
| Secrets | `HARBOR_ROBOT_SECRET` | 로봇 계정 시크릿 |
| Secrets | `MANIFEST_REPO_TOKEN` | 매니페스트 저장소 쓰기 가능한 PAT (Contents: Read and write) |

> 변수 미설정 시(포크 등) 푸시 없이 빌드 검증만 수행합니다.

### 롤백

**이 저장소(앱 코드)에서 `git revert` 후 푸시**하세요 — CI가 새 SHA를 빌드·배포합니다.
매니페스트 저장소의 태그만 되돌리면 다음 앱 푸시가 롤백을 덮어씁니다.
(전제: 레지스트리 보존 정책이 이전 태그 이미지를 지우지 않아야 함)

## 환경 변수 설정 (배포 시 컨테이너에 주입)

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `NCP_ACCESS_KEY` | (필수) | NCP API Access Key |
| `NCP_SECRET_KEY` | (필수) | NCP API Secret Key |
| `SERVER_NAME_FILTER` | "" | 포함할 서버 이름 (쉼표 구분) |
| `SERVER_NAME_EXCLUDE` | "" | 제외할 서버 이름 (쉼표 구분) |
| `NCP_API_URL` | (공공) | NCP API 엔드포인트 URL |
| `DB_PATH` | data/app.db | SQLite DB 파일 경로 (영속화하려면 `/app/data`에 볼륨 마운트) |

> 업무 시간·주말 포함 여부는 env가 아니라 **대시보드 설정 화면**에서 그룹별로 관리합니다 (SQLite 저장).
> 최초 실행 시 "기본 그룹"(09:00~18:00, 주말 제외)이 자동 생성됩니다.

## 스케줄링 동작

- **그룹 단위 관리**: 그룹에 할당된 서버만 자동 시작/중지 대상입니다. 미할당 서버는 자동 관리에서 제외됩니다.
- **자동 시작**: 그룹의 시작 시/분에 도달하면 해당 그룹의 정지된 서버를 시작합니다.
- **자동 중지**: 그룹의 종료 시/분에 도달하면 해당 그룹의 실행 중인 서버를 중지합니다. (설정에서 자동 중지를 끄면 건너뜀)
- **동기화(Sync)**: 사용자가 원할 때 언제든 현재 시간(업무 중/퇴근)에 맞춰 상태를 맞춥니다.
- **수동 조작 우선**: 정해진 트리거 시간 외에는 사용자가 수동으로 켜거나 끈 상태가 유지됩니다.
