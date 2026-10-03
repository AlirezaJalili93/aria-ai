$ErrorActionPreference = 'Stop'

if (-not $env:TEST_DATABASE_URL) {
    throw 'TEST_DATABASE_URL is required for the controlled 0080 E2E.'
}
if (-not $env:TEST_REDIS_URL) {
    throw 'TEST_REDIS_URL is required for the controlled 0080 E2E.'
}

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$apiPython = Join-Path $repositoryRoot 'apps\api\.venv\Scripts\python.exe'
$workerPython = Join-Path $repositoryRoot 'apps\worker\.venv\Scripts\python.exe'
$prepare = Join-Path $PSScriptRoot 'prepare_context_structuring_command.py'
$runtime = Join-Path $PSScriptRoot 'controlled_worker_restart_runtime.py'
$runtimeId = [Guid]::NewGuid().ToString('N')
$runtimeDir = Join-Path $repositoryRoot ".data\aria-0080-$runtimeId"
$checkpointFile = Join-Path $runtimeDir 'checkpoint.json'
$invocationFile = Join-Path $runtimeDir 'invocations.log'
$worker1Out = Join-Path $runtimeDir 'worker-1.out.log'
$worker1Err = Join-Path $runtimeDir 'worker-1.err.log'
$worker2Out = Join-Path $runtimeDir 'worker-2.out.log'
$worker2Err = Join-Path $runtimeDir 'worker-2.err.log'
$worker1 = $null
$worker2 = $null

New-Item -ItemType Directory -Path $runtimeDir | Out-Null

function Confirm-LastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "0080 failed during: $step"
    }
}

function Start-ControlledWorker(
    [string]$number,
    [string]$queueName,
    [string]$eventId,
    [string]$checkpoint,
    [string]$stdoutPath,
    [string]$stderrPath
) {
    $arguments = @(
        "`"$runtime`"",
        'worker',
        '--queue-name', $queueName,
        '--event-id', $eventId,
        '--invocation-file', "`"$invocationFile`"",
        '--worker-number', $number
    )
    if ($checkpoint) {
        $arguments += @('--checkpoint-file', "`"$checkpoint`"")
    }
    return Start-Process `
        -FilePath $workerPython `
        -ArgumentList $arguments `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru
}

function Stop-ControlledWorker($process) {
    if ($null -ne $process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        Wait-Process -Id $process.Id -ErrorAction SilentlyContinue
    }
}

try {
    $setupOutput = & $apiPython $prepare --persisted-synthetic-usage
    Confirm-LastExit 'HTTP command setup'
    $stateLine = $setupOutput | Where-Object { $_ -like 'E2E_STATE=*' } | Select-Object -Last 1
    if (-not $stateLine) {
        throw '0080 setup did not return bounded state identifiers.'
    }
    $state = ($stateLine.Substring('E2E_STATE='.Length) | ConvertFrom-Json)
    $queueName = "aria_0080_$($state.job_id.Replace('-', ''))"

    & $workerPython $runtime relay `
        --queue-name $queueName `
        --job-id $state.job_id `
        --event-id $state.outbox_event_id
    Confirm-LastExit 'Outbox Relay publication'

    $worker1 = Start-ControlledWorker `
        '1' $queueName $state.outbox_event_id $checkpointFile $worker1Out $worker1Err

    $checkpointDeadline = [DateTime]::UtcNow.AddSeconds(45)
    while (-not (Test-Path -LiteralPath $checkpointFile)) {
        if ($worker1.HasExited) {
            throw 'Worker #1 exited before the deterministic pre-Provider checkpoint.'
        }
        if ([DateTime]::UtcNow -ge $checkpointDeadline) {
            throw 'Worker #1 did not reach the deterministic checkpoint.'
        }
        Start-Sleep -Milliseconds 200
    }

    & $workerPython $runtime assert-before `
        --job-id $state.job_id `
        --event-id $state.outbox_event_id `
        --checkpoint-file $checkpointFile `
        --invocation-file $invocationFile
    Confirm-LastExit 'pre-crash state assertion'

    & $workerPython $runtime probe-lock --job-id $state.job_id
    Confirm-LastExit 'concurrent advisory-lock suppression'

    Stop-ControlledWorker $worker1
    $worker1 = $null

    $worker2 = Start-ControlledWorker `
        '2' $queueName $state.outbox_event_id '' $worker2Out $worker2Err

    & $workerPython $runtime wait-after `
        --job-id $state.job_id `
        --event-id $state.outbox_event_id `
        --invocation-file $invocationFile `
        --timeout-seconds 60
    Confirm-LastExit 'Worker #2 redelivery recovery'

    $boundedOutput = @(
        Get-Content -LiteralPath $worker1Out -Raw -ErrorAction SilentlyContinue
        Get-Content -LiteralPath $worker1Err -Raw -ErrorAction SilentlyContinue
        Get-Content -LiteralPath $worker2Out -Raw -ErrorAction SilentlyContinue
        Get-Content -LiteralPath $worker2Err -Raw -ErrorAction SilentlyContinue
    ) -join "`n"
    if ($boundedOutput.Contains('SYNTHETIC_0072_FIXTURE_ONLY')) {
        throw 'Synthetic fixture content leaked through Worker process output.'
    }

    Write-Output 'CONTROLLED_0080_GATE=PASS'
}
finally {
    Stop-ControlledWorker $worker1
    Stop-ControlledWorker $worker2
}
