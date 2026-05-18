# Setup Guide

## Requirements

- Node.js 22+
- npm 10+
- Python 3.10+
- HydraDB API key
- HydraDB tenant ID
- OpenRouter API key for live LLM features

## Install

```powershell
npm install
python -m pip install -r python-sidecar/requirements.txt
```

## Configure Environment

Copy:

```text
.env.example
```

to:

```text
.env
```

Set:

```env
HYDRA_DB_API_KEY=...
HYDRA_DB_TENANT_ID=mq66nfnt5t
HYDRADB_TENANT_ID=mq66nfnt5t
OPENROUTER_API_KEY=...
MY_EMAIL=you@example.com
```

Both tenant variables are included because some tools use `HYDRA_DB_TENANT_ID` and some CLI docs refer to `HYDRADB_TENANT_ID`.

## Run Desktop App

```powershell
npm run dev
```

## Run Sidecar Only

```powershell
npm run sidecar
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

## Run Renderer Only

```powershell
npm exec vite -- src/renderer --host 127.0.0.1 --port 5173
```

## Verify

```powershell
npm run build
node scripts\smoke-renderer.mjs
```

The smoke test writes:

```text
renderer-smoke.json
renderer-smoke.png
```

## HydraDB Verification

If the HydraDB CLI is installed:

```powershell
hydradb whoami
```

For the app itself, the important path is the Python SDK. Confirm installation:

```powershell
python -m pip show hydradb-sdk
```

## Common Issues

### Missing HydraDB Env Vars

The app still runs, but brief generation will use conservative fallback data. Set `HYDRA_DB_API_KEY` and `HYDRA_DB_TENANT_ID`.

### Tenant Not Ready

Tenant creation is asynchronous. If recall or memory writes fail with tenant errors, confirm the tenant exists and infrastructure is ready in HydraDB.

### OpenRouter Missing

HydraDB memory paths can still work, but LLM-generated extraction and brief synthesis will use fallback behavior.

### Playwright Browser Missing

Install Chromium for visual smoke tests:

```powershell
npx playwright install chromium
```
