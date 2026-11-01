# Celery durable Queue candidate evaluation

This is an isolated S1-E02 experiment. It is not the Aria Worker runtime and does not select Celery
for production. It uses a dedicated loopback Redis port and a random per-run password; it never
connects to the hosted Queue.

Run from PowerShell with Docker Desktop available to the current Windows account:

```powershell
Set-Location -LiteralPath 'C:\Users\A.Jalili\Documents\Aria AI\.worktrees\staging-migrations\evals\durable-queue\celery'
.\run-evaluation.ps1
```

The runner verifies that a message published without a worker survives, force-kills the candidate
worker during a long task and checks redelivery, publishes a duplicate business probe and checks
that the probe's idempotent outcome is written once, then measures Redis commands during a ten-second
idle interval. The five-second visibility window and twenty-second task duration are experiment-only
fixtures and are not product defaults.

Each run first removes only the `aria-queue-eval` containers and volume so evidence cannot be
contaminated by a previous attempt. The product Compose stack and its volumes are not addressed.

The runner intentionally leaves the isolated containers and volume available for log inspection.
After evidence has been recorded, remove only this experiment's resources with:

```powershell
$env:QUEUE_EVAL_REDIS_PASSWORD = 'temporary-value-required-only-for-compose-interpolation'
$env:COMPOSE_FILE = (Join-Path $PWD 'compose.yaml')
docker compose down --volumes
```
