$ErrorActionPreference = 'Stop'

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$containerName = "aria-0085-durable-retry-$([Guid]::NewGuid().ToString('N'))"
$database = 'aria_0085_test'
$previousDatabaseUrl = $env:DATABASE_URL
$previousTestDatabaseUrl = $env:TEST_DATABASE_URL
$previousUvCacheDir = $env:UV_CACHE_DIR

function Confirm-LastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "0085 failed during: $step"
    }
}

try {
    docker run --detach --rm `
        --name $containerName `
        --env POSTGRES_HOST_AUTH_METHOD=trust `
        --publish 127.0.0.1::5432 `
        postgres:16-alpine | Out-Null
    Confirm-LastExit 'isolated PostgreSQL startup'

    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        docker exec $containerName pg_isready --username postgres --dbname postgres | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        if ([DateTime]::UtcNow -ge $deadline) {
            throw 'Isolated PostgreSQL did not become ready.'
        }
        Start-Sleep -Milliseconds 250
    } while ($true)

    $portOutput = docker port $containerName '5432/tcp'
    Confirm-LastExit 'isolated PostgreSQL port resolution'
    if (($portOutput | Out-String).Trim() -notmatch ':(\d+)$') {
        throw 'Unable to resolve isolated PostgreSQL host port.'
    }
    $hostPort = $Matches[1]
    docker exec $containerName createdb --username postgres $database
    Confirm-LastExit 'database creation'

    $env:UV_CACHE_DIR = Join-Path $repositoryRoot '.uv-cache'
    $env:DATABASE_URL = "postgresql://postgres@127.0.0.1:$hostPort/$database"
    $env:TEST_DATABASE_URL = $env:DATABASE_URL
    & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini upgrade head
    Confirm-LastExit 'fresh migration upgrade'

    & node scripts/run-uv.mjs --project apps/worker run pytest -q `
        apps/worker/tests/test_ai_invocation_recovery.py `
        apps/worker/tests/test_ai_invocation_recovery_postgres.py `
        apps/worker/tests/test_context_structuring_runtime_postgres.py::test_durable_timeout_retry_persists_two_attempts_and_two_usage_records `
        apps/worker/tests/test_context_structuring_runtime_postgres.py::test_crash_after_failed_known_reuses_schedule_and_never_reinvokes_attempt_zero `
        apps/worker/tests/test_context_structuring_runtime_postgres.py::test_second_timeout_is_terminal_and_never_creates_attempt_two
    Confirm-LastExit 'durable retry, crash recovery and isolation matrix'

    docker exec $containerName psql --username postgres --dbname $database `
        --command 'TRUNCATE public.accounts CASCADE' | Out-Null
    Confirm-LastExit 'downgrade fixture cleanup'
    & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini downgrade 0032_ai01_checkpoint_integration
    Confirm-LastExit '0033 downgrade'
    & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini upgrade head
    Confirm-LastExit '0033 re-upgrade'

    Write-Output 'CONTROLLED_0085_GATE=PASS'
}
finally {
    foreach ($item in @(
        @{ Name = 'DATABASE_URL'; Value = $previousDatabaseUrl },
        @{ Name = 'TEST_DATABASE_URL'; Value = $previousTestDatabaseUrl },
        @{ Name = 'UV_CACHE_DIR'; Value = $previousUvCacheDir }
    )) {
        if ($null -eq $item.Value) {
            Remove-Item "Env:$($item.Name)" -ErrorAction SilentlyContinue
        }
        else {
            Set-Item "Env:$($item.Name)" $item.Value
        }
    }
    docker stop $containerName | Out-Null
}
