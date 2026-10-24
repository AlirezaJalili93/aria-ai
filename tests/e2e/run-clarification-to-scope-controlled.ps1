$ErrorActionPreference = 'Stop'

if (-not $env:TEST_DATABASE_URL) {
    throw 'TEST_DATABASE_URL is required for the controlled 0082 E2E.'
}
if (-not $env:TEST_REDIS_URL) {
    throw 'TEST_REDIS_URL is required for the controlled 0082 E2E.'
}

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$apiPython = Join-Path $repositoryRoot 'apps\api\.venv\Scripts\python.exe'
$workerPython = Join-Path $repositoryRoot 'apps\worker\.venv\Scripts\python.exe'
$harness = Join-Path $PSScriptRoot 'controlled_context_to_scope_api.py'

& $apiPython $harness --clarification-resolution
if ($LASTEXITCODE -ne 0) {
    throw 'The controlled Clarification-to-Scope journey failed.'
}

& $apiPython -m pytest -q `
    apps/api/tests/test_clarification_postgres.py `
    apps/api/tests/test_scope_generation_jobs_postgres.py `
    apps/api/tests/test_synthetic_runtime_tenant_isolation_postgres.py
if ($LASTEXITCODE -ne 0) {
    throw 'The Clarification/Scope PostgreSQL replay and tenant gate failed.'
}

& $workerPython -m pytest -q `
    apps/worker/tests/test_generation_input_locks_postgres.py `
    apps/worker/tests/test_scope_generation_runtime_postgres.py `
    apps/worker/tests/test_synthetic_runtime_tenant_isolation_postgres.py
if ($LASTEXITCODE -ne 0) {
    throw 'The Scope Worker pinning/rollback/duplicate-delivery gate failed.'
}

Write-Output 'CONTROLLED_0082_GATE=PASS'
