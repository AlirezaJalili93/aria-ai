# Owned Local/Synthetic PostgreSQL + Redis gate; optional disposable Browser, no Hosted.
param([switch]$BrowserGate, [switch]$BrowserCasesOnly)
$ErrorActionPreference = 'Stop'
if ($BrowserCasesOnly -and -not $BrowserGate) { throw 'BrowserCasesOnly requires BrowserGate' }
$joinedRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$joinedIdentity = [Guid]::NewGuid().ToString('N')
$joinedPostgres = 'aria-0102-joined-pg-' + $joinedIdentity
$joinedRedis = 'aria-0102-joined-redis-' + $joinedIdentity
$joinedTemporary = Join-Path $joinedRoot ('.tmp/preview-joined-' + $joinedIdentity)
$joinedPrevious = @{}
foreach ($joinedVariable in @('DATABASE_URL','TEST_DATABASE_URL','TEST_QUEUE_BROKER_URL','TEST_PREVIEW_BROWSER','TMP','TEMP')) {
    $joinedPrevious[$joinedVariable] = [Environment]::GetEnvironmentVariable($joinedVariable, 'Process')
}
$joinedPgStarted = $false
$joinedRedisStarted = $false
function Confirm-JoinedExit([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "Controlled joined Preview gate failed: $step" }
}
Push-Location -LiteralPath $joinedRoot
try {
    New-Item -ItemType Directory -Path $joinedTemporary | Out-Null
    $env:TMP = $joinedTemporary
    $env:TEMP = $joinedTemporary
    docker run --detach --rm --name $joinedPostgres --env POSTGRES_HOST_AUTH_METHOD=trust `
        --publish 127.0.0.1::5432 postgres:16-alpine | Out-Null
    Confirm-JoinedExit 'owned PostgreSQL startup'
    $joinedPgStarted = $true
    docker run --detach --rm --name $joinedRedis --publish 127.0.0.1::6379 redis:7-alpine | Out-Null
    Confirm-JoinedExit 'owned Redis startup'
    $joinedRedisStarted = $true
    $joinedDeadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        docker exec $joinedPostgres pg_isready --username postgres | Out-Null
        $joinedPgReady = $LASTEXITCODE -eq 0
        docker exec $joinedRedis redis-cli ping | Out-Null
        $joinedRedisReady = $LASTEXITCODE -eq 0
        if ($joinedPgReady -and $joinedRedisReady) { break }
        if ([DateTime]::UtcNow -ge $joinedDeadline) { throw 'Owned services not ready' }
        Start-Sleep -Milliseconds 250
    } while ($true)
    $joinedPgBinding = (docker port $joinedPostgres '5432/tcp' | Out-String).Trim()
    Confirm-JoinedExit 'owned PostgreSQL port'
    if ($joinedPgBinding -notmatch '^127\.0\.0\.1:(\d+)$') { throw 'Non-loopback PostgreSQL rejected' }
    $joinedPgPort = $Matches[1]
    $joinedRedisBinding = (docker port $joinedRedis '6379/tcp' | Out-String).Trim()
    Confirm-JoinedExit 'owned Redis port'
    if ($joinedRedisBinding -notmatch '^127\.0\.0\.1:(\d+)$') { throw 'Non-loopback Redis rejected' }
    $joinedRedisPort = $Matches[1]
    docker exec $joinedPostgres psql --username postgres --command 'CREATE DATABASE aria_0102_joined' | Out-Null
    Confirm-JoinedExit 'new synthetic database'
    $env:DATABASE_URL = 'postgresql+asyncpg://postgres@127.0.0.1:' + $joinedPgPort + '/aria_0102_joined?ssl=disable'
    $env:TEST_DATABASE_URL = $env:DATABASE_URL
    $env:TEST_QUEUE_BROKER_URL = 'redis://127.0.0.1:' + $joinedRedisPort + '/0'
    $env:TEST_PREVIEW_BROWSER = if ($BrowserGate) { 'controlled-synthetic-browser' } else { $null }
    node scripts/run-uv.mjs --project apps/api run alembic --config apps/api/alembic.ini upgrade head
    Confirm-JoinedExit 'existing reviewed migrations'
    $joinedPytestArguments = @('-q','--tb=short','apps/worker/tests/test_preview_delivery_postgres_redis.py')
    if ($BrowserCasesOnly) { $joinedPytestArguments += @('-k','True-False') }
    node scripts/run-uv.mjs --project apps/worker run pytest @joinedPytestArguments
    Confirm-JoinedExit 'actual relay, broker, principal, copy/recovery/replay tests'
    if ($BrowserCasesOnly) { Write-Output 'FOCUSED_BROWSER_CASES_ONLY=PASS; FULL_JOINED_MATRIX=NOT_EVALUATED' }
    else {
        Write-Output 'PREVIEW_JOINED_RELAY_WORKER_SUBGATE=PASS'
        Write-Output 'APPLICATION_COMMAND_RELAY_WORKER_HTTP_SUBGATE=PASS'
    }
    if ($BrowserGate) { Write-Output 'THREE_PROJECT_TYPE_SYNTHETIC_BROWSER=PASS' }
    else { Write-Output 'BROWSER=NOT_EVALUATED' }
    Write-Output 'MANAGEMENT_HTTP_JWT=OUT_OF_SCOPE'
}
finally {
    foreach ($joinedVariable in $joinedPrevious.Keys) {
        [Environment]::SetEnvironmentVariable($joinedVariable, $joinedPrevious[$joinedVariable], 'Process')
    }
    if ($joinedRedisStarted) {
        docker stop $joinedRedis | Out-Null
        Confirm-JoinedExit 'owned Redis cleanup'
    }
    if ($joinedPgStarted) {
        docker stop $joinedPostgres | Out-Null
        Confirm-JoinedExit 'owned PostgreSQL cleanup'
    }
    if (Test-Path -LiteralPath $joinedTemporary) {
        $joinedResolvedTemporary = (Resolve-Path -LiteralPath $joinedTemporary).Path
        $joinedAllowedPrefix = Join-Path $joinedRoot '.tmp/preview-joined-'
        if (-not $joinedResolvedTemporary.StartsWith($joinedAllowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Owned joined temporary cleanup rejected'
        }
        Remove-Item -LiteralPath $joinedResolvedTemporary -Recurse -Force
    }
    Pop-Location
}
