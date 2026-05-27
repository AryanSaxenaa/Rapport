import { create } from 'zustand'
import type {
  RecordingStartResult,
  ImapConfig,
  ImapResult,
} from '../shared/types'

export type DepStatus = { ok: boolean; reason: string | null }

export type SidecarStatusDeps = {
  hydradb: DepStatus
  openrouter: DepStatus
  microphone: DepStatus
  imap: DepStatus
}

export type GraphNode = {
  id: string
  label: string
  importance: number
  type: 'person'
}

export type EvidenceItem = {
  quote: string
  date: string
}

export type GraphEdge = {
  from: string
  to: string
  type: string
  weight: number
  color: 'red' | 'amber' | 'green' | 'grey'
  evidence: EvidenceItem[]
}

export type GraphData = {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export type Stance = 'champion' | 'skeptic' | 'neutral' | 'blocker'

export type Brief = {
  contactName: string
  company: string
  currentStance: Stance
  stanceShiftNote?: string
  topConcerns: string[]
  communicationStyle: string
  talkingPoints: string[]
  landmines: string[]
  lastInteraction: string
  powerNote: string
}

export type Commitment = {
  owner: string
  what: string
  status: 'open' | 'closed'
  due?: string
  source_quote?: string
}

export type UnresolvedItem = {
  holder: string
  awaiting_from: string
  what: string
  since?: string
}

export type Contact = {
  contactEmail: string
  contactName: string
  company: string
  stance: Stance
  lastInteraction?: string
  topics?: string[]
  sentimentShift?: string
  commitments?: Commitment[]
  unresolved?: UnresolvedItem[]
  summary?: string
}

export type ContactsResponse = {
  contacts?: Contact[]
  source?: string
  warning?: string
  error?: string
}

export const SIDECAR_URL = 'http://127.0.0.1:8765'
export const SIDECAR_WS_URL = 'ws://127.0.0.1:8765'

const sidecarRequest = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${SIDECAR_URL}${path}`, init)
  if (!response.ok) throw new Error(`Sidecar ${response.status}: ${await response.text()}`)
  return response.json() as Promise<T>
}

type RapportState = {
  isRecording: boolean
  sidecarStatus: 'checking' | 'online' | 'offline'
  commandOpen: boolean
  settingsOpen: boolean
  activeBrief: Brief | null
  briefLoading: boolean
  liveTranscript: string[]
  detectedContacts: string[]
  selectedContact: Contact
  contacts: Contact[]
  contactsLoading: boolean
  contactsError: string | null
  contactsSource: string | null
  minimized: boolean
  graphData: GraphData
  depStatus: SidecarStatusDeps | null
  setSidecarStatus: (value: RapportState['sidecarStatus']) => void
  setCommandOpen: (value: boolean) => void
  setSettingsOpen: (value: boolean) => void
  setActiveBrief: (brief: Brief | null) => void
  setMinimized: (value: boolean) => void
  pushTranscript: (line: string) => void
  setSelectedContact: (contact: Contact) => void
  fetchContacts: () => Promise<void>
  fetchGraph: () => Promise<void>
  fetchDepStatus: () => Promise<void>
  configureSidecar: (keys: Record<string, string>) => Promise<void>
  ingestImap: (cfg: ImapConfig) => Promise<{ count: number }>
  startRecording: (contact: Contact) => Promise<RecordingStartResult>
  stopRecording: () => Promise<void>
  fetchBrief: (contactEmail: string, contactName: string, company: string) => Promise<Brief | null>
}

export const defaultContact: Contact = {
  contactEmail: '',
  contactName: 'No contact selected',
  company: '',
  stance: 'neutral',
}

export const useRapportStore = create<RapportState>((set, get) => ({
  isRecording: false,
  sidecarStatus: 'checking',
  commandOpen: false,
  settingsOpen: false,
  minimized: false,
  activeBrief: null,
  briefLoading: false,
  liveTranscript: ['Waiting for meeting audio.', 'Relationship signals will appear here as Rapport listens.'],
  detectedContacts: [],
  selectedContact: defaultContact,
  contacts: [],
  contactsLoading: false,
  contactsError: null,
  contactsSource: null,
  graphData: { nodes: [], edges: [] },
  depStatus: null,

  setSidecarStatus: (value) => set({ sidecarStatus: value }),
  setCommandOpen: (value) => set({ commandOpen: value }),
  setSettingsOpen: (value) => set({ settingsOpen: value }),
  setActiveBrief: (brief) => set({ activeBrief: brief }),
  setMinimized: (value) => set({ minimized: value }),
  pushTranscript: (line) =>
    // BUG-32: Store keeps last 4 lines (UI shows last 2) — previously kept
    // 8 lines that were never rendered, wasting memory.
    set((state) => ({ liveTranscript: [...state.liveTranscript.slice(-3), line] })),
  setSelectedContact: (contact) => set({ selectedContact: contact }),

  fetchContacts: async () => {
    set({ contactsLoading: true, contactsError: null })
    try {
      const data = await sidecarRequest<ContactsResponse>('/contacts')
      const contacts = data?.contacts?.filter((c) => c.contactEmail && c.contactName) ?? []
      set({
        contacts,
        contactsLoading: false,
        contactsSource: data?.source ?? null,
        contactsError: data?.error ?? data?.warning ?? null,
        selectedContact: contacts.length > 0 ? contacts[0] : defaultContact,
      })
    } catch (err) {
      set({
        contacts: [],
        contactsLoading: false,
        contactsSource: null,
        contactsError: `Failed to load contacts: sidecar unreachable. ${String(err)}`,
        selectedContact: defaultContact,
      })
    }
  },

  fetchGraph: async () => {
    try {
      const data = await sidecarRequest<GraphData>('/graph')
      set({ graphData: data })
    } catch (err) {
      console.warn('Rapport: graph fetch failed', err)
    }
  },

  fetchDepStatus: async () => {
    try {
      const data = await sidecarRequest<SidecarStatusDeps>('/status')
      set({ depStatus: data })
    } catch (err) {
      set({ depStatus: null })
      console.warn('Rapport: dep status fetch failed (sidecar offline?)', err)
    }
  },

  configureSidecar: async (keys: Record<string, string>) => {
    await sidecarRequest('/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(keys),
    })
    // Refresh dep status after configure
    const data = await sidecarRequest<SidecarStatusDeps>('/status').catch((err) => {
      console.warn('Rapport: status refresh after configure failed', err)
      return null
    })
    if (data) set({ depStatus: data })
  },

  ingestImap: async (cfg) => {
    const data = await sidecarRequest<ImapResult>('/ingest/imap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    })
    return { count: data.count ?? 0 }
  },

  startRecording: async (contact) => {
    const result = await sidecarRequest<RecordingStartResult>('/recording/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(contact),
    })
    if (result.status === 'recording') set({ isRecording: true })
    return result
  },

  stopRecording: async () => {
    await sidecarRequest('/recording/stop', { method: 'POST' })
    set({ isRecording: false })
  },

  fetchBrief: async (contactEmail, contactName, company) => {
    set({ briefLoading: true })
    try {
      const params = new URLSearchParams({ contact_name: contactName, company })
      const brief = await sidecarRequest<Brief>(`/brief/${encodeURIComponent(contactEmail)}?${params}`)
      set({ activeBrief: brief, briefLoading: false })
      return brief
    } catch {
      set({ briefLoading: false })
      return null
    }
  },
}))
