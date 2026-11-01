$ErrorActionPreference = 'Stop'

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$containerName = "aria-0084-ai01-checkpoint-$([Guid]::NewGuid().ToString('N'))"
$database = 'aria_0084_test'
$previousDatabaseUrl = $env:DATABASE_URL
$previousTestDatabaseUrl = $env:TEST_DATABASE_URL
$previousUvCacheDir = $env:UV_CACHE_DIR

function Confirm-LastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "0084 failed during: $step"
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
        apps/worker/tests/test_context_structuring_checkpoint.py `
        apps/worker/tests/test_context_structuring_runtime_postgres.py::test_checkpoint_recovery_finalizes_same_attempt_without_second_invocation `
        apps/worker/tests/test_ai_invocation_recovery_postgres.py::test_worker_cannot_delete_checkpoint_or_target_another_tenant
    Confirm-LastExit 'AI-01 checkpoint recovery and isolation matrix'

    & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini downgrade 0031_ai_invocation_checkpoints
    Confirm-LastExit '0032 index downgrade'
    & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini upgrade head
    Confirm-LastExit '0032 index re-upgrade'

    Write-Output 'CONTROLLED_0084_GATE=PASS'
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
