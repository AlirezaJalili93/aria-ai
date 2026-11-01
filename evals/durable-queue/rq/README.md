# RQ durable Queue candidate evaluation

This is an isolated S1-E02 experiment. It is not the Aria Worker runtime and does not select RQ for
the product. The one-second maintenance/monitoring intervals, 16-second Worker TTL, one retry and
short delay are experiment fixtures, not approved production defaults. The short Worker TTL reduces
the idle dequeue block so native registry maintenance can run after an abandoned Job lease expires.

The candidate uses RQ's JSON serializer explicitly because RQ documents `pickle` as its insecure
default. Forced Worker loss may take about 61 seconds to become eligible for abandoned-job cleanup;
the runner does not manipulate Redis time or registry scores to create a false-fast recovery result.

Run from an authenticated Windows PowerShell whose Docker Desktop Linux engine is available:

```powershell
Set-Location -LiteralPath 'C:\Users\A.Jalili\Documents\Aria AI\.worktrees\staging-migrations\evals\durable-queue\rq'
.\run-evaluation.ps1
```

The runner uses a dedicated Compose project, loopback port, volume and random per-run Redis
credential. It intentionally leaves the stack running so Redis command evidence can be inspected;
run `docker compose down --volumes --remove-orphans` from the same PowerShell session before clearing
the generated environment variables if cleanup is required.
