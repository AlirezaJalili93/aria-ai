[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$randomBytes = New-Object byte[] 24
$randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $randomGenerator.GetBytes($randomBytes)
}
finally {
    $randomGenerator.Dispose()
}
$env:QUEUE_EVAL_REDIS_PASSWORD = -join ($randomBytes | ForEach-Object { $_.ToString('x2') })
$env:COMPOSE_FILE = (Join-Path $PSScriptRoot 'compose.yaml')

function Confirm-LastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "RQ evaluation failed during: $step"
    }
}

try {
    docker compose down --volumes --remove-orphans
    Confirm-LastExit 'isolated environment reset'

    docker compose up -d --build redis
    Confirm-LastExit 'redis startup'

    docker compose run --rm probe reset
    Confirm-LastExit 'isolated state reset'

    Write-Output 'candidate=rq probe=worker-absent phase=publish'
    docker compose run --rm probe publish --probe-id worker-absent
    Confirm-LastExit 'worker-absent publish'

    Start-Sleep -Seconds 2
    docker compose run --rm probe wait --probe-id worker-absent --min-attempts 0 --max-attempts 0 --outcomes 0 --no-finished --timeout-seconds 1
    Confirm-LastExit 'worker-absent precondition'

    docker compose up -d --build queue-eval-worker
    Confirm-LastExit 'worker startup'

    docker compose run --rm probe wait --probe-id worker-absent --min-attempts 1 --outcomes 1 --finished --timeout-seconds 45
    Confirm-LastExit 'worker-absent recovery'

    Write-Output 'candidate=rq probe=exception-retry phase=publish'
    docker compose run --rm probe publish --probe-id exception-retry --fail-first-attempt
    Confirm-LastExit 'exception-retry publish'
    docker compose run --rm probe wait --probe-id exception-retry --min-attempts 2 --outcomes 1 --finished --timeout-seconds 45
    Confirm-LastExit 'exception retry'

    Write-Output 'candidate=rq probe=forced-worker-loss phase=publish'
    docker compose run --rm probe publish --probe-id forced-worker-loss --sleep-seconds 20
    Confirm-LastExit 'forced-worker-loss publish'

    docker compose run --rm probe wait --probe-id forced-worker-loss --min-attempts 1 --outcomes 0 --no-finished --timeout-seconds 15
    Confirm-LastExit 'forced-worker-loss started'

    docker compose kill queue-eval-worker
    Confirm-LastExit 'forced worker kill'
    docker compose up -d queue-eval-worker
    Confirm-LastExit 'forced worker restart'

    Write-Output 'candidate=rq note=abandoned-job-recovery-may-take-about-61-seconds'
    docker compose run --rm probe wait --probe-id forced-worker-loss --min-attempts 2 --outcomes 1 --finished --timeout-seconds 100
    Confirm-LastExit 'forced worker redelivery'

    Write-Output 'candidate=rq probe=duplicate-delivery phase=publish-twice'
    docker compose run --rm probe publish --probe-id duplicate-delivery
    Confirm-LastExit 'duplicate publish one'
    docker compose run --rm probe publish --probe-id duplicate-delivery
    Confirm-LastExit 'duplicate publish two'
    docker compose run --rm probe wait --probe-id duplicate-delivery --min-attempts 2 --outcomes 1 --finished --timeout-seconds 45
    Confirm-LastExit 'duplicate outcome guard'

    Write-Output 'candidate=rq probe=delayed-delivery phase=publish'
    docker compose run --rm probe publish --probe-id delayed-delivery --delay-seconds 3
    Confirm-LastExit 'delayed publish'
    docker compose run --rm probe wait --probe-id delayed-delivery --min-attempts 0 --max-attempts 0 --outcomes 0 --no-finished --timeout-seconds 1
    Confirm-LastExit 'delayed precondition'
    docker compose run --rm probe wait --probe-id delayed-delivery --min-attempts 1 --outcomes 1 --finished --timeout-seconds 15
    Confirm-LastExit 'delayed delivery'

    docker compose run --rm probe idle-measure --seconds 10
    Confirm-LastExit 'idle-command-delta measurement'

    Write-Output 'RQ_EVALUATION_RESULT=PASS'
}
finally {
    $env:QUEUE_EVAL_REDIS_PASSWORD = $null
    $env:COMPOSE_FILE = $null
}
