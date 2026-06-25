# 폐쇄망(대상)에서 실행 → 번들로 오프라인 설치. 사전조건: Python 3.14 + uv 설치됨, deploy\bundle 복사됨.
$ErrorActionPreference = "Stop"
$deploy = $PSScriptRoot
$root = Split-Path -Parent $deploy
$wheelhouse = Join-Path $deploy "bundle\wheelhouse"
$req = Join-Path $deploy "bundle\requirements-offline.txt"

if (-not (Test-Path $wheelhouse)) { throw "wheelhouse 없음: $wheelhouse (번들을 복사했는지 확인)" }

Push-Location $root
try {
    Write-Host "[1/3] 가상환경 생성"
    uv venv

    Write-Host "[2/3] 의존성 오프라인 설치(인터넷 미사용)"
    uv pip install --no-index --find-links $wheelhouse -r $req

    Write-Host "[3/3] 프로젝트 설치(콘솔 스크립트 등록)"
    uv pip install --no-index --no-deps -e .
}
finally { Pop-Location }

Write-Host ""
Write-Host "설치 완료. 다음을 수행하세요:"
Write-Host "  1) deploy\.env.offline.example 를 프로젝트 루트의 .env 로 복사 후 절대경로를 환경에 맞게 수정"
Write-Host "  2) 검증:  uv run cluster-screening <zip|폴더|pdf> --name 테스트"
Write-Host "  3) RAG:   data\reference\ 에 근거 문서 넣고  uv run rag-index"
