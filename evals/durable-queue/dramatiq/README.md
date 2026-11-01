# Dramatiq durable Queue candidate evaluation

This is an isolated S1-E02 experiment. It is not the Aria Worker runtime and does not select
Dramatiq for the product. The five-second heartbeat and short delay are experiment fixtures, not
approved production defaults.

Run from an authenticated Windows PowerShell whose Docker Desktop Linux engine is available:

```powershell
Set-Location -LiteralPath 'C:\Users\A.Jalili\Documents\Aria AI\.worktrees\staging-migrations\evals\durable-queue\dramatiq'
.\run-evaluation.ps1
```

The runner uses a dedicated Compose project, loopback port, volume and random per-run Redis
credential. It intentionally leaves the stack running so Redis command evidence can be inspected;
run `docker compose down --volumes --remove-orphans` from the same PowerShell session before clearing
the generated environment variables if cleanup is required.
