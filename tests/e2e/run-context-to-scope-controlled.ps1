$ErrorActionPreference = 'Stop'

if (-not $env:TEST_DATABASE_URL) {
    throw 'TEST_DATABASE_URL is required for the controlled 0077 E2E.'
}
if (-not $env:TEST_REDIS_URL) {
    throw 'TEST_REDIS_URL is required for the controlled 0077 E2E.'
}

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$apiPython = Join-Path $repositoryRoot 'apps\api\.venv\Scripts\python.exe'
$workerPython = Join-Path $repositoryRoot 'apps\worker\.venv\Scripts\python.exe'
$harness = Join-Path $PSScriptRoot 'controlled_context_to_scope_api.py'

# Prove the entry point rejects a non-dedicated database before migration/reset.
$dedicatedUrl = $env:TEST_DATABASE_URL
try {
    $env:TEST_DATABASE_URL = 'postgresql+asyncpg://invalid@127.0.0.1/aria_not_0077'
    $ErrorActionPreference = 'Continue'
    $rejected = & $apiPython $harness 2>&1
    $guardExit = $LASTEXITCODE
    if ($guardExit -eq 0 -or -not (($rejected | Out-String) -match 'SAFE_API_ERROR_CLASS=DedicatedTestDatabaseRequired')) {
        throw 'The non-test database guard did not reject before mutation.'
    }
} finally {
    $ErrorActionPreference = 'Stop'
    $env:TEST_DATABASE_URL = $dedicatedUrl
}

& $apiPython $harness
if ($LASTEXITCODE -ne 0) {
    throw 'The controlled synthetic Context-to-Scope journey failed.'
}

& $apiPython -m pytest -q `
    apps/api/tests/test_scope_generation_jobs_postgres.py `
    apps/api/tests/test_synthetic_runtime_tenant_isolation_postgres.py
if ($LASTEXITCODE -ne 0) {
    throw 'The PostgreSQL scheduling/tenant negative gate failed.'
}

& $workerPython -m pytest -q `
    apps/worker/tests/test_generation_input_locks_postgres.py `
    apps/worker/tests/test_scope_generation_runtime_postgres.py `
    apps/worker/tests/test_synthetic_runtime_tenant_isolation_postgres.py
if ($LASTEXITCODE -ne 0) {
    throw 'The PostgreSQL Worker replay/pinning/rollback/tenant negative gate failed.'
}

Write-Output 'CONTROLLED_0077_NEGATIVE_GATE=PASS'
