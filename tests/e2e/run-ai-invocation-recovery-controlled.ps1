$ErrorActionPreference = 'Stop'

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$containerName = "aria-0083-recovery-$([Guid]::NewGuid().ToString('N'))"
$database = 'aria_0083_test'
$previousDatabaseUrl = $env:DATABASE_URL
$previousTestDatabaseUrl = $env:TEST_DATABASE_URL
$previousUvCacheDir = $env:UV_CACHE_DIR

function Confirm-LastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "0083 failed during: $step"
    }
}

function Invoke-Postgres([string]$sql) {
    $output = docker exec $containerName psql `
        --username postgres `
        --dbname $database `
        --tuples-only `
        --no-align `
        --command $sql
    Confirm-LastExit 'PostgreSQL command'
    return ($output | Out-String).Trim()
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
        apps/worker/tests/test_ai_invocation_recovery_postgres.py
    Confirm-LastExit 'PostgreSQL crash/recovery matrix'

    $ErrorActionPreference = 'Continue'
    $downgradeOutput = & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini downgrade 0030_generation_input_row_locks 2>&1
    $downgradeExitCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($downgradeExitCode -eq 0) {
        throw '0031 downgrade unexpectedly discarded durable checkpoint evidence.'
    }
    if (($downgradeOutput | Out-String) -notmatch
        'cannot downgrade while AI invocation checkpoints exist') {
        throw '0031 downgrade failed for an unexpected reason.'
    }

    Invoke-Postgres 'TRUNCATE public.ai_invocation_checkpoints, public.usage_records' | Out-Null
    & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini downgrade 0030_generation_input_row_locks
    Confirm-LastExit 'clean checkpoint downgrade'
    & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini upgrade head
    Confirm-LastExit 'checkpoint re-upgrade'

    if ((Invoke-Postgres @"
SELECT count(*) FROM pg_catalog.pg_tables
WHERE schemaname='public' AND tablename='ai_invocation_checkpoints'
"@) -ne '1') {
        throw 'Checkpoint table is absent after migration recovery.'
    }

    Write-Output 'CONTROLLED_0083_GATE=PASS'
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
