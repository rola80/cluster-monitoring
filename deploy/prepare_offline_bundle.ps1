# 인터넷 되는 PC에서 실행 → deploy\bundle 에 오프라인 번들(wheelhouse + 모델 + NLTK) 생성.
# 사전조건: 이 PC에서 `uv sync --extra rag --extra unstructured` 가 끝나 있어야 함(모델 다운로드 위함).
# 대상(폐쇄망)과 동일 플랫폼(Windows x64)에서 실행해야 wheel이 호환된다.
$ErrorActionPreference = "Stop"
$deploy = $PSScriptRoot
$root = Split-Path -Parent $deploy
$bundle = Join-Path $deploy "bundle"
$wheelhouse = Join-Path $bundle "wheelhouse"
New-Item -ItemType Directory -Force -Path $bundle, $wheelhouse | Out-Null

Push-Location $root
try {
    Write-Host "[1/3] 의존성 잠금 → requirements 추출"
    # 프로젝트 자체는 제외(소스로 별도 설치). rag+unstructured extra 포함.
    uv export --frozen --no-hashes --no-emit-project --extra rag --extra unstructured `
        -o "$bundle\requirements-offline.txt"

    Write-Host "[2/3] wheelhouse 생성(휠 수집/빌드) — 용량이 큽니다(torch 등)"
    # pip를 일시 포함해 모든 의존성 휠을 모은다(동일 플랫폼 기준).
    uv run --with pip python -m pip wheel -r "$bundle\requirements-offline.txt" -w $wheelhouse

    Write-Host "[3/3] 모델/데이터 다운로드"
    uv run --with pip python "$deploy\_fetch_models.py" $bundle
}
finally { Pop-Location }

Write-Host ""
Write-Host "번들 완료: $bundle"
Write-Host "이 폴더(또는 프로젝트 전체)를 폐쇄망으로 복사한 뒤, 대상에서 deploy\install_offline.ps1 실행."
