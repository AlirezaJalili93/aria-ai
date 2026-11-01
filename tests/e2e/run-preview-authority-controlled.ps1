# 0102 Local/Synthetic database authority gate. No Hosted/provider/browser activation.
param([switch]$FullRegression)
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$containerName = "aria-0102-authority-$([Guid]::NewGuid().ToString('N'))"
$databaseName = 'aria_0102_gate'
$previousDatabaseUrl = $env:DATABASE_URL
$previousTestDatabaseUrl = $env:TEST_DATABASE_URL
$started = $false
$previousPreviewTmp = $env:TMP
$previousPreviewTemp = $env:TEMP
$previewTemporary = Join-Path $repositoryRoot ('.tmp/preview-0102-' + [Guid]::NewGuid().ToString('N'))

function Confirm-LastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "0102 authority gate failed during: $step" }
}

Push-Location -LiteralPath $repositoryRoot
try {
    New-Item -ItemType Directory -Path $previewTemporary -Force | Out-Null
    $env:TMP = $previewTemporary
    $env:TEMP = $previewTemporary
    docker run --detach --rm --name $containerName `
        --env POSTGRES_HOST_AUTH_METHOD=trust `
        --publish 127.0.0.1::5432 postgres:16-alpine | Out-Null
    Confirm-LastExit 'throwaway PostgreSQL startup'
    $started = $true
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        docker exec $containerName pg_isready --username postgres --dbname postgres | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        if ([DateTime]::UtcNow -ge $deadline) { throw 'Throwaway PostgreSQL not ready' }
        Start-Sleep -Milliseconds 250
    } while ($true)
    $binding = (docker port $containerName '5432/tcp' | Out-String).Trim()
    Confirm-LastExit 'loopback port resolution'
    if ($binding -notmatch '^127\.0\.0\.1:(\d+)$') { throw 'Non-loopback binding rejected' }
    $hostPort = $Matches[1]
    docker exec $containerName psql --username postgres --dbname postgres `
        --command "CREATE DATABASE $databaseName" | Out-Null
    Confirm-LastExit 'empty synthetic database creation'
    # This throwaway trust-auth loopback instance has no TLS; never change product TLS policy.
    $env:DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:$hostPort/${databaseName}?ssl=disable"
    $env:TEST_DATABASE_URL = $env:DATABASE_URL
    node scripts/run-uv.mjs --project apps/api run alembic --config apps/api/alembic.ini upgrade head
    Confirm-LastExit 'fresh migration chain'
    node scripts/run-uv.mjs --project apps/api run pytest -q --tb=short `
        apps/api/tests/test_preview_authority_postgres.py `
        apps/api/tests/test_preview_publication_postgres.py `
        apps/api/tests/test_preview_migration_postgres.py `
        apps/api/tests/test_preview_failure_postgres.py `
        apps/api/tests/test_account_bootstrap_postgres.py::test_identity_revision_downgrades_and_reapplies_cleanly
    Confirm-LastExit 'actual aria_worker authority, capability and guarded rollback tests'
    node scripts/run-uv.mjs --project apps/worker run pytest -q --tb=short `
        apps/worker/tests/test_preview_publication_runtime_postgres.py
    Confirm-LastExit 'actual aria_worker real-bundle preparation and controlled copy recovery'
    if ($FullRegression) {
        node scripts/run-uv.mjs --project apps/api run pytest -q --tb=short apps/api/tests
        Confirm-LastExit 'complete disposable PostgreSQL API regression'
        node scripts/run-uv.mjs --project apps/worker run pytest -q --tb=short apps/worker/tests
        Confirm-LastExit 'complete disposable PostgreSQL Worker regression'
        Write-Output 'PREVIEW_FULL_POSTGRESQL_REGRESSION=PASS'
    }
    Write-Output 'PREVIEW_DATABASE_AUTHORITY_GATE=PASS'
    Write-Output 'PREVIEW_GUARDED_DOWNGRADE_GATE=PASS'
    Write-Output 'PREVIEW_WORKER_COPY_SUBGATE=PASS'
    Write-Output 'PREVIEW_APPLICATION_ACCESS_SUBGATE=PASS'
    Write-Output 'PREVIEW_FAILURE_HELPER_GATE=PASS'
    Write-Output 'FULL_0102_PUBLISHING_BROWSER_GATE=NOT_EVALUATED'
}
finally {
    $env:TMP = $previousPreviewTmp
    $env:TEMP = $previousPreviewTemp
    if ($null -eq $previousDatabaseUrl) {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    } else { $env:DATABASE_URL = $previousDatabaseUrl }
    if ($null -eq $previousTestDatabaseUrl) {
        Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
    } else { $env:TEST_DATABASE_URL = $previousTestDatabaseUrl }
    if ($started) {
        # Exact container created by this invocation only; --rm discards synthetic test state.
        docker stop $containerName | Out-Null
        Confirm-LastExit 'synthetic container cleanup'
    }
    if (Test-Path -LiteralPath $previewTemporary) {
        $resolvedPreviewTemporary = (Resolve-Path -LiteralPath $previewTemporary).Path
        $expectedPreviewTemporary = Join-Path $repositoryRoot '.tmp/preview-0102-'
        if (-not $resolvedPreviewTemporary.StartsWith($expectedPreviewTemporary, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Preview temporary cleanup target rejected'
        }
        Remove-Item -LiteralPath $resolvedPreviewTemporary -Recurse -Force
    }
    Pop-Location
}
