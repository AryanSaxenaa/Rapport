# Rapport — Improvement Plan

Tracks all changes to fix reliability, connect-UX, correctness, and code-quality issues.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` skipped

---

## P0 — Data integrity & honesty (stop lying to user)

Highest priority. Current code writes fabricated data into HydraDB and renders fake structure in UI.

- [x] **B1. Kill simulated transcript pollution** — `python-sidecar/audio_capture.py`
  - Delete `_simulate_transcript` method entirely.
  - Collapse 4 fall-through branches in `_capture_loop` into one early `raise RecordingDisabled(reason)`.
  - `main.py:64-82` `/recording/start` catches and returns `{status: "disabled", reason}`.
  - UI surfaces reason in a banner (no silent fake "Mira/Priya" lines).

- [x] **B2. Stop inventing fake topics** — `python-sidecar/entity_extractor.py`
  - `fallback_extraction` returns empty lists, no hardcoded `["security","rollout","budget"]`.
  - When fallback triggers, caller (`main.py:_extract_and_store`, `ingest_emails_background`) skips the HydraDB write rather than store empty extraction.

- [x] **O2. Surface background-task failures** — `python-sidecar/main.py`
  - `asyncio.create_task(_extract_and_store(...))` gets `add_done_callback` that pushes errors to WS.
  - Same for ingestion loop.

- [x] **B3. Decision: KEEP, REBUILD AS EVIDENCE-BACKED SEMANTIC GRAPH** (2026-05-24)
  - Reject: current index-chain edges (`App.tsx:114-135`).
  - Reject: deleting the panel.
  - **Reject (per user, 2026-05-24): co-occurrence, "same email thread", "shared keywords", "shared company".** These produce decorative noise, damage credibility.
  - **Graph must answer five questions:**
    1. Who matters?
    2. Why?
    3. How recently?
    4. How strongly?
    5. What unresolved context exists?
    6. Who influences whom?
  - **Edges = directed, typed, evidence-backed. Every edge cites a source.**
    - `approves(A -> B, decision)` — A holds approval power over B's decision
    - `blocks(A -> B, decision)` — A is blocking B's progress on X
    - `escalates_to(A -> B)` — A escalates decisions up to B
    - `influences(A -> B, topic)` — A explicitly changed B's stance / drove B's position
    - `committed_to(A -> X, status, due)` — A owes a deliverable, open or closed
    - `awaits_from(A -> B, what)` — A is waiting on B; unresolved
    - `endorsed_by(A -> B)` — A vouched for B in writing
  - Every edge record carries: `evidence_text` (exact quote), `source_id` (HydraDB chunk), `date`, `confidence` (0–1).
  - **No edge without evidence. No co-occurrence edges. No keyword-overlap edges.**
  - **Node importance score** (drives node size + sort order):
    - `importance = w1·unresolved_items_held + w2·decisions_influenced + w3·recency_decay(last_interaction) + w4·in_degree(approves/escalates_to)`
    - Tunable weights, sensible defaults.
  - **Edge weight** = evidence_count × recency_decay. Drives stroke width.
  - **Color coding:**
    - Red: `blocks`, open `awaits_from` (unresolved drag)
    - Amber: open `committed_to`, pending `approves`
    - Green: completed commitments, granted approvals
    - Grey: `escalates_to`, `endorsed_by` (structural, not status-bearing)
  - **Extraction schema rewrite** — `python-sidecar/entity_extractor.py`:
    - LLM prompt returns `{relations: [{from, to, type, evidence, date, confidence}], commitments: [{owner, what, status, due, source_quote}], unresolved: [{holder, awaiting_from, what, since}]}`.
    - Store each relation as a typed HydraDB memory with `additional_metadata.relation_type` + source quote.
    - Replace the current flat `topics`/`stance` shape.
  - **Backend** — new `python-sidecar/relationship_graph.py`:
    - `build_graph(client) -> Graph` — queries HydraDB for all relation records, deduplicates by `(from, to, type)`, accumulates evidence list, computes weights + node importance.
    - New endpoint `GET /graph` returns `{nodes: [{id, label, importance, type}], edges: [{from, to, type, weight, status, evidence: [{quote, source_id, date}]}]}`.
  - **Frontend** — `src/renderer/src/components/RelationshipGraph.tsx`:
    - Directed edges (arrows).
    - Node size ∝ importance. Edge stroke width ∝ weight. Color per status.
    - Click edge → side panel with evidence quotes + source links.
    - Click node → ContactCard surfaces that contact's unresolved items + held decisions.
    - Empty state when `edges.length === 0`: "Not enough evidence yet — ingest more emails or record a call." **Never invent edges.**
  - **Verification:**
    - Unit test: zero ingestion → zero edges rendered. No chain edges.
    - Unit test: edge without evidence array is rejected at backend boundary.
    - Manual: ingest a known email thread, confirm extracted relation matches actual content.

---

## P1 — Connect UX (eliminate the gcloud dance)

Current Gmail flow requires: create gcloud project → enable API → OAuth consent screen → desktop client → download `credentials.json` → place in `python-sidecar/` → run setup script. 30+ min, hostile.

- [x] **Gmail strategy decision: C (both), strict priority** (2026-05-24)
  - **PRIMARY: `.eml` / `.mbox` import** — zero auth, ships first, works offline.
  - **SECONDARY: IMAP sync** — per-user app-password, opt-in, second milestone.
  - **OAuth: postponed.** Existing `gmail_reader.py` + `setup_gmail_auth.py` stay dormant; remove from default install path. Do not delete code yet — revisit after PRIMARY+SECONDARY ship.
  - **Rationale:** import flow has no failure modes — no API quota, no token refresh, no consent screen, no gcloud project. Demo-able in ten seconds. IMAP fills the "keep current" gap once import proves the data model.

- [x] **PRIMARY — `.eml` / `.mbox` import**
  - New endpoint `POST /ingest/file` accepting multipart upload OR JSON `{path}`.
  - New `python-sidecar/email_file_reader.py`:
    - `parse_eml(bytes) -> Email` and `parse_mbox(bytes) -> Iterator[Email]` using stdlib `email`/`mailbox`.
    - Returns the same `Email` shape `gmail_reader._parse_email_message` produces, so downstream extraction stays unchanged.
  - Renderer: drag-and-drop target on the shell. On drop, POST to sidecar, stream progress over WS.
  - Handles HTML-only emails (closes S3 gap automatically).
  - Verification: drop a known `.mbox`, confirm extracted relations match content.

- [ ] **SECONDARY — IMAP sync**
  - New `python-sidecar/imap_reader.py` using stdlib `imaplib` (no third-party deps).
  - Settings UI captures: host, port (default 993), username, app-password, "since" cutoff.
  - Credentials stored via OS keychain (`keyring` lib), **never** in `.env` or plaintext file.
  - Endpoint `POST /ingest/imap` runs a one-shot sync; later add scheduled poll.
  - Validate connection before save; surface clear errors (auth fail, TLS fail, host wrong).

- [ ] **OAuth path — postpone, do not delete**
  - Keep `gmail_reader.py`, `calendar_poller.py`, `setup_gmail_auth.py` in repo for future revival.
  - Remove from README quick-start and SETUP.md. Move references to a `docs/OAUTH_POSTPONED.md` note explaining the decision.
  - Calendar polling unaffected for now (revisit during P4 onboarding).

- [ ] **Settings panel in UI**
  - Connection status for each dependency: mic, transcription, HydraDB, mail.
  - Each line shows: green/red + last-error reason.
  - No more "is the sidecar running?" guesswork.

---

## P2 — Structural code quality (thermo-nuclear findings)

### Repository / API layer

- [x] **B4. Decompose `list_contacts`** — extracted to `contact_repository.py`
  - Create `python-sidecar/contact_repository.py`:
    - `iter_from_sub_tenants(client) -> AsyncIterator[Contact]`
    - `iter_from_full_recall(client) -> AsyncIterator[Contact]`
    - `_normalize(meta, fallback_email) -> Contact` (canonical, replace 3 duplicates)
  - `list_contacts` becomes ~15 lines: merge local + 2 iterators through one dedup.

- [x] **B5. Drop lossy sub-tenant-id decoder**
  - `_sub_tenant_id` encoder is lossy (`foo.bar` and `foo_bar` collide after decode).
  - Always read email from `metadata.contact_email`. Treat sub-tenant id as opaque.
  - Delete `contact_from_sub_id`.

### Electron / IPC layer

- [x] **J1. Delete IPC pass-through layer**
  - `src/main/index.ts:133-159` — remove handlers: `get-contacts`, `ingest-emails`, `get-brief`, `start-recording`, `stop-recording`.
  - `src/preload/index.ts:4-11` — remove matching exports.
  - `src/renderer/src/store/rapport-store.ts:74-97` — remove `window.electron?.X` branches; renderer fetches sidecar directly.
  - Keep only `minimize-window` / `restore-window` (real native).
  - Saves ~70 lines.

- [x] **J3. Extract `useSidecarSocket` hook** — `src/renderer/src/App.tsx:33-107`
  - 72 lines of WS lifecycle out of UI component.
  - New file: `src/renderer/src/hooks/useSidecarSocket.ts`.

### Python sidecar shared helpers

- [x] **J2. Collapse two Google OAuth flows**
  - `gmail_reader.py:18-47` and `calendar_poller.py:22-51` are line-for-line duplicates.
  - New `python-sidecar/google_oauth.py::get_service(api, version, scopes, token_filename)`.
  - Each caller becomes 1 line.

- [x] **J4. Extract `parse_model_list(env_var, default)`**
  - `hydradb_client.py:19-23` and `entity_extractor.py:14-18` duplicate comma-split logic.

### Type contracts

- [ ] **T1. Replace `dict[str, Any]` with dataclasses in sidecar**
  - `RecordingSession`, `ExtractedSignals`, `Contact`, `RecallChunk`, `RecallResult`.
  - Keep HydraDB SDK Pydantic models where possible; remove `_to_plain_data` in hot paths.

- [ ] **T2. Type `contact: unknown` properly** — `src/preload/index.ts:4`
  - Use shared `Contact` type from store.

- [ ] **S1. Wrap module-global state in `main.py`**
  - `recording_session` -> `RecordingSession` dataclass instance.
  - `connected_clients` -> `ConnectionManager` with `broadcast(payload)`.

### Functional gaps

- [ ] **S3. Handle HTML-only emails** — `python-sidecar/gmail_reader.py:50-63`
  - Current `_parse_email_payload` returns first `text/plain`. HTML-only multipart -> dropped.
  - Add `text/html` strip fallback (`html.parser` or `BeautifulSoup`).

- [ ] **O1. Parallelize email ingestion** — `python-sidecar/main.py:273-285`
  - Currently sequential: 50 × ~3s = 150s wall-time.
  - `asyncio.gather` with concurrency cap (e.g. semaphore of 5).

### UI surfacing

- [ ] **Rewrite ContactCard to show recall content** — `src/renderer/src/components/ContactCard.tsx`
  - Currently: name/company/email/last-date only.
  - Add: topics, last N interaction summaries, commitments, stance reasoning.
  - Pull from `/contacts` response (extend backend to include richer fields per contact).

### Styling

- [ ] **F3. Decide CSS strategy** — `src/renderer/src/styles/nothing-theme.css` (906 lines)
  - File imports Tailwind on line 2 but uses zero utility classes.
  - Option A: commit to Tailwind, shrink CSS dramatically.
  - Option B: drop `@import "tailwindcss"` and `@tailwindcss/vite` dep.
  - If staying with custom CSS: split into per-section files before adding any new panel.

---

## P3 — Trivial UI bug

- [x] **Right-side empty rectangle** — `src/renderer/src/styles/nothing-theme.css`
  - `.control-surface { width: min(100%, 426px) }` + window width 460 + shell padding 14 = 20px dead band.
  - Fix: `width: 100%` (drop the 426 cap) or expand to match window content.

---

## P4 — Distribution (later)

For "easily downloadable":

- [ ] **Bundle Python sidecar with PyInstaller**
  - Single `.exe`/`.dmg` so users don't need Python+pip.

- [ ] **electron-builder config**
  - Generate Windows installer + macOS dmg.
  - Signed binaries (cert needed).

- [ ] **Auto-updater**
  - `electron-updater` with GitHub releases.

- [ ] **First-run onboarding wizard**
  - HydraDB key, OpenRouter key, mail strategy chosen above.
  - Store via OS keychain, not `.env`.

---

## Decision log

Capture choices made during execution:

- 2026-05-24 — Initial plan created from thermo-nuclear review.
- 2026-05-24 — B3: graph kept, rebuilt as evidence-backed semantic graph. Co-occurrence/keyword/thread edges explicitly rejected.
- 2026-05-24 — Gmail strategy: C (both). PRIMARY = .eml/.mbox import, SECONDARY = IMAP, OAuth postponed.

---

## Out of scope (decisions to revisit)

- Calendar polling (`calendar_poller.py`) — does it earn its keep? Currently fires briefs on upcoming meetings. Keep or cut?
- Brief generation via OpenRouter — locked into one provider, no offline fallback. Acceptable for now.
