$ErrorActionPreference = 'Stop'

if (-not $env:TEST_DATABASE_URL) {
    throw 'TEST_DATABASE_URL is required for the controlled 0078 E2E.'
}
if (-not $env:TEST_REDIS_URL) {
    throw 'TEST_REDIS_URL is required for the controlled 0078 E2E.'
}

# The baseline runner proves the database guard, existing journey and negative
# PostgreSQL gates before the edit-specific scenario resets the same test DB.
& (Join-Path $PSScriptRoot 'run-context-to-scope-controlled.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'The approved 0077 baseline gate failed.'
}

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$apiPython = Join-Path $repositoryRoot 'apps\api\.venv\Scripts\python.exe'
$harness = Join-Path $PSScriptRoot 'controlled_context_to_scope_api.py'
& $apiPython $harness --requirement-edit
if ($LASTEXITCODE -ne 0) {
    throw 'The controlled Requirement-edit-to-Scope journey failed.'
}

Write-Output 'CONTROLLED_0078_GATE=PASS'
