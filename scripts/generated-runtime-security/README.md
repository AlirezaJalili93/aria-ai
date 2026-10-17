# 0098 Generated Runtime Security Review

The disposable harness rebuilds the exact 0097 static-export candidate from the same Prototype
writer and pinned dependencies. It adds a versioned adversarial corpus, static Artifact checks,
high/critical dependency gating, a read-only local server and Chrome DevTools Protocol runtime
observation/blocking.

```powershell
npm run test:generated-runtime-security
npm run proof:generated-runtime-security
```

The Browser Gate accepts only same-origin GET/HEAD static requests, exact AST Page navigation and
allowlisted fixture images. It starts with a fresh profile, no credential and no persistent product
state. Production CSP, iframe sandbox flags, domain isolation and Hosted Preview remain explicitly
unevaluated.
