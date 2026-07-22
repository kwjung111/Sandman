# NCP Server Manager - Docker 빌드 & Harbor 푸시 (Windows)
#
# 사용법:
#   .\build_push.ps1                # build.env 설정으로 빌드 + 푸시
#   .\build_push.ps1 -NoPush        # 빌드만
#   .\build_push.ps1 -Tag v1.2.0    # 태그 지정
#
# 설정 우선순위: CLI 인자 > 환경변수 > build.env 파일
# 레지스트리 로그인은 미리 한 번 해두세요:  docker login <registry>

param(
    [string]$Tag = "",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. build.env 로드 (있으면). 이미 설정된 환경변수는 덮어쓰지 않음
$envFile = Join-Path $PSScriptRoot "build.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*)\s*$' -and -not $_.StartsWith('#')) {
            $key = $Matches[1]; $val = $Matches[2].Trim()
            if ($val -ne "" -and -not (Test-Path "env:$key")) {
                Set-Item -Path "env:$key" -Value $val
            }
        }
    }
}

# 2. 필수 값 검증
if (-not $env:REGISTRY) {
    Write-Host "[ERROR] REGISTRY 가 설정되지 않았습니다." -ForegroundColor Red
    Write-Host "  cp build.env.example build.env  후 값을 채우거나,"
    Write-Host "  `$env:REGISTRY = 'harbor.example.com' 으로 지정하세요."
    exit 1
}
$project = if ($env:REGISTRY_PROJECT) { $env:REGISTRY_PROJECT } else { "library" }
$imageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "ncp-server-manager" }

# 3. 태그 결정: CLI 인자 > IMAGE_TAG env > git short hash > latest
#    커밋 안 된 변경이 있으면 -dirty 접미사 (이미지와 커밋 불일치 표시)
if (-not $Tag) { $Tag = $env:IMAGE_TAG }
if (-not $Tag) {
    $Tag = (git rev-parse --short HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $Tag) {
        $Tag = "latest"
    } else {
        git diff --quiet HEAD 2>$null
        if ($LASTEXITCODE -ne 0) { $Tag = "$Tag-dirty" }
    }
}

$fullImage = "$($env:REGISTRY)/$project/${imageName}:$Tag"

Write-Host "=============================================="
Write-Host " 이미지: $fullImage"
Write-Host " 푸시:   $(if ($NoPush) { '안 함 (빌드만)' } else { $env:REGISTRY })"
Write-Host "=============================================="

# 4. 빌드
docker build -t $fullImage -t "$($env:REGISTRY)/$project/${imageName}:latest" .
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 빌드 실패. Docker Desktop이 실행 중인지 확인하세요." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] 빌드 완료" -ForegroundColor Green

if ($NoPush) { exit 0 }

# 5. 푸시 (버전 태그 + latest)
docker push $fullImage
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 푸시 실패. 'docker login $($env:REGISTRY)' 로 로그인했는지, 사내망(VPN) 연결 상태를 확인하세요." -ForegroundColor Red
    exit 1
}
docker push "$($env:REGISTRY)/$project/${imageName}:latest"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] latest 태그 푸시 실패." -ForegroundColor Red
    exit 1
}

Write-Host "=============================================="
Write-Host "[SUCCESS] 푸시 완료:" -ForegroundColor Green
Write-Host "  $fullImage"
Write-Host "  $($env:REGISTRY)/$project/${imageName}:latest"
Write-Host ""
Write-Host "[서버에서 실행]"
Write-Host "  docker pull $fullImage"
Write-Host "  ./start.sh   (start.sh의 이미지명도 레지스트리 경로로 지정)"
Write-Host "=============================================="
