# API Reference

The Python sidecar runs at `http://127.0.0.1:8765` and exposes a REST + WebSocket API.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/status` | Dependency status (HydraDB, OpenRouter, Microphone, IMAP) |
| GET | `/contacts` | List contacts from HydraDB + local cache |
| GET | `/graph` | Relationship graph data |
| GET | `/brief/{email}?contact_name=...&company=...` | Generate pre-call brief for a contact |
| POST | `/configure` | Save API keys to `.env` |
| POST | `/recording/start` | Start live audio capture |
| POST | `/recording/stop` | Stop live audio capture |
| POST | `/ingest/file` | Upload `.eml` / `.mbox` files |
| POST | `/ingest/emails` | Trigger Gmail ingestion |
| POST | `/ingest/imap` | Trigger IMAP sync (saves credentials) |
| GET | `/imap/credentials` | List stored IMAP hosts |
| POST | `/imap/credentials/use` | Re-use stored IMAP credentials |
| DELETE | `/imap/credentials` | Delete stored IMAP credentials |
| DELETE | `/data/transcripts` | Clear transcript buffer |
| DELETE | `/data/contacts` | Delete local contacts |
| DELETE | `/data/all` | Delete all local data |
| WS | `/ws/transcript` | WebSocket for live transcript, briefs, errors |

## Quick test

```bash
curl http://127.0.0.1:8765/health
```

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```
