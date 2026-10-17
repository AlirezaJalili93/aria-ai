# Local/Synthetic Redis transport subgate; no PostgreSQL/Hosted/customer activation.
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$previewQueueContainer = 'aria-0102-queue-' + [Guid]::NewGuid().ToString('N')
$previousPreviewBroker = $env:TEST_QUEUE_BROKER_URL
$previewQueueStarted = $false
function Confirm-PreviewQueueExit([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "Controlled Preview queue gate failed: $step" }
}
Push-Location -LiteralPath $repositoryRoot
try {
    docker run --detach --rm --name $previewQueueContainer `
        --publish 127.0.0.1::6379 redis:7-alpine | Out-Null
    Confirm-PreviewQueueExit 'owned loopback Redis startup'
    $previewQueueStarted = $true
    $queueDeadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        docker exec $previewQueueContainer redis-cli ping | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        if ([DateTime]::UtcNow -ge $queueDeadline) { throw 'Owned Redis not ready' }
        Start-Sleep -Milliseconds 250
    } while ($true)
    $queueBinding = (docker port $previewQueueContainer '6379/tcp' | Out-String).Trim()
    Confirm-PreviewQueueExit 'owned Redis port resolution'
    if ($queueBinding -notmatch '^127\.0\.0\.1:(\d+)$') { throw 'Non-loopback Redis rejected' }
    $env:TEST_QUEUE_BROKER_URL = 'redis://127.0.0.1:' + $Matches[1] + '/0'
    node scripts/run-uv.mjs --project apps/worker run pytest -q --tb=short `
        apps/worker/tests/test_preview_queue.py apps/worker/tests/test_preview_queue_redis.py `
        apps/worker/tests/test_outbox_publisher.py apps/worker/tests/test_celery_runtime.py
    Confirm-PreviewQueueExit 'fixed envelope, isolated task and actual Redis transport tests'
    Write-Output 'PREVIEW_CONTROLLED_QUEUE_TRANSPORT=PASS'
    Write-Output 'POSTGRESQL_TO_BROWSER_E2E=NOT_EVALUATED'
}
finally {
    if ($null -eq $previousPreviewBroker) {
        Remove-Item Env:TEST_QUEUE_BROKER_URL -ErrorAction SilentlyContinue
    } else { $env:TEST_QUEUE_BROKER_URL = $previousPreviewBroker }
    if ($previewQueueStarted) {
        # Exact --rm container created here only, including its synthetic broker state.
        docker stop $previewQueueContainer | Out-Null
        Confirm-PreviewQueueExit 'owned Redis cleanup'
    }
    Pop-Location
}
