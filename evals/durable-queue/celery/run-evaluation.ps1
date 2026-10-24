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
        throw "Queue evaluation failed during: $step"
    }
}

try {
    docker compose down --volumes --remove-orphans
    Confirm-LastExit 'isolated environment reset'

    docker compose up -d --build redis
    Confirm-LastExit 'redis startup'

    docker compose run --rm probe reset
    Confirm-LastExit 'isolated state reset'

    Write-Output 'probe=worker-absent phase=publish'
    docker compose run --rm probe publish --probe-id worker-absent --sleep-seconds 0
    Confirm-LastExit 'worker-absent publish'

    Start-Sleep -Seconds 2
    docker compose run --rm probe wait --probe-id worker-absent --min-attempts 0 --outcomes 0 --no-finished --timeout-seconds 1
    Confirm-LastExit 'worker-absent precondition'

    docker compose up -d --build queue-eval-worker
    Confirm-LastExit 'worker startup'

    docker compose run --rm probe wait --probe-id worker-absent --min-attempts 1 --outcomes 1 --finished --timeout-seconds 45
    Confirm-LastExit 'worker-absent recovery'

    Write-Output 'probe=forced-worker-loss phase=publish'
    docker compose run --rm probe publish --probe-id forced-worker-loss --sleep-seconds 20
    Confirm-LastExit 'forced-worker-loss publish'

    docker compose run --rm probe wait --probe-id forced-worker-loss --min-attempts 1 --outcomes 0 --no-finished --timeout-seconds 15
    Confirm-LastExit 'forced-worker-loss started'

    docker compose kill queue-eval-worker
    Confirm-LastExit 'forced worker kill'
    Start-Sleep -Seconds 7
    docker compose up -d queue-eval-worker
    Confirm-LastExit 'forced worker restart'

    docker compose run --rm probe wait --probe-id forced-worker-loss --min-attempts 2 --outcomes 1 --finished --timeout-seconds 45
    Confirm-LastExit 'forced worker redelivery'

    Write-Output 'probe=duplicate-delivery phase=publish-twice'
    docker compose run --rm probe publish --probe-id duplicate-delivery --sleep-seconds 0
    Confirm-LastExit 'duplicate publish one'
    docker compose run --rm probe publish --probe-id duplicate-delivery --sleep-seconds 0
    Confirm-LastExit 'duplicate publish two'
    docker compose run --rm probe wait --probe-id duplicate-delivery --min-attempts 2 --outcomes 1 --finished --timeout-seconds 45
    Confirm-LastExit 'duplicate outcome guard'

    docker compose run --rm probe idle-measure --seconds 10
    Confirm-LastExit 'idle-command-delta measurement'

    Write-Output 'QUEUE_EVALUATION_RESULT=PASS'
}
finally {
    $env:QUEUE_EVAL_REDIS_PASSWORD = $null
    $env:COMPOSE_FILE = $null
}
