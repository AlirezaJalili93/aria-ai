$ErrorActionPreference = 'Stop'

if (-not $env:TEST_DATABASE_URL) {
    throw 'TEST_DATABASE_URL is required for the controlled synthetic E2E.'
}

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$apiPython = Join-Path $repositoryRoot 'apps\api\.venv\Scripts\python.exe'
$workerPython = Join-Path $repositoryRoot 'apps\worker\.venv\Scripts\python.exe'
$prepare = Join-Path $PSScriptRoot 'prepare_context_structuring_command.py'
$complete = Join-Path $PSScriptRoot 'complete_context_structuring_command.py'

$apiOutput = & $apiPython $prepare
if ($LASTEXITCODE -ne 0) {
    throw 'Controlled synthetic API preparation failed.'
}
$stateLine = $apiOutput | Where-Object { $_ -like 'E2E_STATE=*' } | Select-Object -Last 1
if (-not $stateLine) {
    throw 'Controlled synthetic API state was not emitted.'
}
$state = ($stateLine -replace '^E2E_STATE=', '') | ConvertFrom-Json

& $workerPython $complete `
    --account-id $state.account_id `
    --project-id $state.project_id `
    --job-id $state.job_id `
    --outbox-event-id $state.outbox_event_id
if ($LASTEXITCODE -ne 0) {
    throw 'Controlled synthetic Worker completion failed.'
}
