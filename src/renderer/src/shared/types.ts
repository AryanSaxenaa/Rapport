/**
 * Shared types for Rapport — WebSocket messages and API shapes
 * used across the renderer (hooks, components, store).
 *
 * Domain types (Contact, Brief, GraphNode, etc.) live in
 * src/renderer/src/store/rapport-store.ts as the single source of truth.
 */

export type WsTranscriptMessage = {
  type: 'transcript'
  text: string
}

export type WsBriefMessage = {
  type: 'brief'
  data: unknown
}

export type WsErrorMessage = {
  type: 'error'
  message: string
}

export type WsIngestCompleteMessage = {
  type: 'ingest_complete'
  count: number
}

export type WsMessage =
  | WsTranscriptMessage
  | WsBriefMessage
  | WsErrorMessage
  | WsIngestCompleteMessage

export type RecordingStartResult = {
  status: 'recording' | 'disabled'
  reason?: string
}

export type ImapConfig = {
  host: string
  port: number
  username: string
  password: string
  since_days: number
}

export type ImapResult = {
  count: number
  status: string
}
