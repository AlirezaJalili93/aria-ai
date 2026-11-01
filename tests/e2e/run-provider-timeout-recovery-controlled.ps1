$ErrorActionPreference = 'Stop'

if (-not $env:TEST_DATABASE_URL) {
    throw 'TEST_DATABASE_URL is required for the controlled 0079 E2E.'
}
if (-not $env:TEST_REDIS_URL) {
    throw 'TEST_REDIS_URL is required for the controlled 0079 E2E.'
}

# Preserve the accepted baseline and PostgreSQL negative gates before the
# timeout scenario resets the same dedicated throwaway database.
& (Join-Path $PSScriptRoot 'run-context-to-scope-controlled.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'The accepted 0077 baseline gate failed.'
}

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$apiPython = Join-Path $repositoryRoot 'apps\api\.venv\Scripts\python.exe'
$harness = Join-Path $PSScriptRoot 'controlled_context_to_scope_api.py'
& $apiPython $harness --provider-timeout-retry
if ($LASTEXITCODE -ne 0) {
    throw 'The controlled Provider-timeout recovery journey failed.'
}

Write-Output 'CONTROLLED_0079_GATE=PASS'
