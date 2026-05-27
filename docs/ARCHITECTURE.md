# Architecture

## Overview

Rapport is a local-first desktop app with a Python intelligence sidecar.

```mermaid
flowchart TB
  subgraph Desktop["Electron Desktop App"]
    Main["Main Process"]
    Renderer["React Renderer"]
    Preload["Secure Preload Bridge"]
  end

  subgraph Sidecar["FastAPI Sidecar"]
    API["REST + WebSocket API"]
    Capture["Audio Capture"]
    Extract["Entity Extraction"]
    Hydra["HydraDB Client"]
    Brief["Brief Generator"]
  end

  Renderer <--> Preload
  Preload <--> Main
  Main <--> API
  API --> Capture
  API --> Extract
  API --> Hydra
  Hydra --> Brief
  Brief --> API
  API --> Renderer
```

## Components

### Electron Main

Location:

```text
src/main/index.ts
```

Responsibilities:

- creates the floating desktop window
- spawns the Python sidecar
- exposes IPC handlers
- owns tray actions
- keeps secrets out of the renderer

### React Renderer

Location:

```text
src/renderer/src
```

Responsibilities:

- floating orb UI
- live capture strip
- pre-call brief panel
- command bar
- relationship graph
- local UI state

### FastAPI Sidecar

Location:

```text
python-sidecar
```

Responsibilities:

- transcript processing
- LLM extraction
- HydraDB writes and recall
- Gmail ingestion
- Calendar polling
- WebSocket push to the overlay

## Data Flow

### Call Capture

```mermaid
sequenceDiagram
  participant UI as React Overlay
  participant API as FastAPI Sidecar
  participant LLM as Extraction Model
  participant H as HydraDB

  UI->>API: POST /recording/start
  API->>UI: WebSocket transcript events
  API->>LLM: extract stance, topics, commitments
  LLM-->>API: structured relationship signals
  API->>H: upload.add_memory
  H-->>API: memory stored
```

### Pre-Call Brief

```mermaid
sequenceDiagram
  participant UI as React Overlay
  participant API as FastAPI Sidecar
  participant H as HydraDB
  participant LLM as Brief Model

  UI->>API: GET /brief/{contact_email}
  API->>H: recall_preferences
  API->>H: full_recall
  H-->>API: memory + knowledge context
  API->>LLM: synthesize tactical brief
  LLM-->>API: structured brief JSON
  API-->>UI: pre-call brief
```

## Design Principles

- The renderer never talks to HydraDB directly.
- The sidecar owns every external API call.
- HydraDB stores durable relationship memory.
- The app remains runnable with fallback data when keys are absent.
- The UI is compact because the product is meant to live beside meetings, not replace them.

## Security Posture

- API keys live in environment variables or `.env`.
- Secrets are not exposed through the preload bridge.
- Gmail tokens should be stored outside the app bundle.
- Recording state is visible in the UI.
- Future production builds should add explicit meeting opt-in and local transcript retention controls.
