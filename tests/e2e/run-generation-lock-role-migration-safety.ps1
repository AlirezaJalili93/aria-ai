$ErrorActionPreference = 'Stop'

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$containerName = "aria-0081-migration-$([Guid]::NewGuid().ToString('N'))"
$databaseA = 'aria_0081_a'
$databaseB = 'aria_0081_b'
$databaseMismatch = 'aria_0081_mismatch'
$previousDatabaseUrl = $env:DATABASE_URL

function Confirm-LastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "0081 failed during: $step"
    }
}

function Invoke-Postgres([string]$database, [string]$sql) {
    $output = docker exec $containerName psql `
        --username postgres `
        --dbname $database `
        --tuples-only `
        --no-align `
        --command $sql
    Confirm-LastExit "PostgreSQL command on $database"
    return ($output | Out-String).Trim()
}

function Invoke-Migration([string]$database, [string]$direction, [string]$revision) {
    $env:DATABASE_URL = "postgresql://postgres@127.0.0.1:$hostPort/$database"
    & node scripts/run-uv.mjs --project apps/api run alembic `
        --config apps/api/alembic.ini $direction $revision
    Confirm-LastExit "Alembic $direction $revision on $database"
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
        if ($LASTEXITCODE -eq 0) {
            break
        }
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

    foreach ($database in ($databaseA, $databaseB, $databaseMismatch)) {
        Invoke-Postgres 'postgres' "CREATE DATABASE $database" | Out-Null
    }

    Invoke-Migration $databaseA 'upgrade' 'head'
    Invoke-Migration $databaseB 'upgrade' 'head'

    $roleState = Invoke-Postgres 'postgres' @"
SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole,
       rolreplication, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname='aria_generation_lock_owner'
"@
    if ($roleState -ne 'f|f|f|f|f|f|f') {
        throw "Unexpected generation lock owner attributes: $roleState"
    }

    foreach ($database in ($databaseA, $databaseB)) {
        $functionCount = Invoke-Postgres $database @"
SELECT count(*)
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='aria_internal'
  AND p.proname IN ('lock_requirement_generation_inputs', 'lock_gap_detection_inputs')
"@
        if ($functionCount -ne '2') {
            throw "Expected both generation lock helpers in $database."
        }
    }

    Invoke-Migration $databaseB 'downgrade' '0029_scope_generation_runtime'
    if ((Invoke-Postgres 'postgres' @"
SELECT count(*) FROM pg_catalog.pg_roles
WHERE rolname='aria_generation_lock_owner'
"@) -ne '1') {
        throw 'First database downgrade removed a Role still used by another database.'
    }
    if ((Invoke-Postgres $databaseA @"
SELECT count(*)
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='aria_internal'
  AND p.proname IN ('lock_requirement_generation_inputs', 'lock_gap_detection_inputs')
"@) -ne '2') {
        throw 'First database downgrade damaged the other database helpers.'
    }

    Invoke-Migration $databaseA 'downgrade' '0029_scope_generation_runtime'
    if ((Invoke-Postgres 'postgres' @"
SELECT count(*) FROM pg_catalog.pg_roles
WHERE rolname='aria_generation_lock_owner'
"@) -ne '0') {
        throw 'Last database downgrade did not remove the unused dedicated Role.'
    }

    Invoke-Postgres 'postgres' @"
CREATE ROLE aria_generation_lock_owner LOGIN NOINHERIT NOSUPERUSER
NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
"@ | Out-Null
    $env:DATABASE_URL =
        "postgresql://postgres@127.0.0.1:$hostPort/$databaseMismatch"
    try {
        $ErrorActionPreference = 'Continue'
        $mismatchOutput = & node scripts/run-uv.mjs --project apps/api run alembic `
            --config apps/api/alembic.ini upgrade head 2>&1
        $mismatchExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = 'Stop'
    }
    if ($mismatchExitCode -eq 0) {
        throw 'Migration accepted an incompatible pre-existing Role.'
    }
    if (($mismatchOutput | Out-String) -notmatch
        'generation lock owner role attributes rejected') {
        throw 'Migration failed for an unexpected reason instead of the Role contract.'
    }
    if ((Invoke-Postgres $databaseMismatch @"
SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname='aria_internal'
"@) -ne '0') {
        throw 'Fail-closed Role validation left database-local 0030 objects behind.'
    }

    Write-Output 'GENERATION_LOCK_ROLE_MIGRATION_GATE=PASS'
}
finally {
    if ($null -eq $previousDatabaseUrl) {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }
    else {
        $env:DATABASE_URL = $previousDatabaseUrl
    }
    docker stop $containerName | Out-Null
}
