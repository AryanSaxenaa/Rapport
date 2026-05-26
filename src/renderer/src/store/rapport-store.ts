import { create } from 'zustand'

export type DepStatus = { ok: boolean; reason: string | null }

export type SidecarStatus_Deps = {
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

export type Contact = {
  contactEmail: string
  contactName: string
  company: string
  stance: Stance
  lastInteraction?: string
  topics?: string[]
}

type ContactsResponse = {
  contacts?: Contact[]
  source?: 'hydradb' | 'local' | 'demo' | string
  warning?: string
  error?: string
}

const SIDECAR_URL = 'http://127.0.0.1:8765'

const demoContacts: Contact[] = [
  {
    contactEmail: 'mira.voss@northstar-ledger.example',
    contactName: 'Mira Voss',
    company: 'Northstar Ledger',
    stance: 'skeptic',
    lastInteraction: new Date().toISOString().slice(0, 10),
    topics: ['security review', 'rollout workload', 'budget timing'],
  },
  {
    contactEmail: 'jon.bell@apexfoundry.example',
    contactName: 'Jon Bell',
    company: 'Apex Foundry',
    stance: 'champion',
    lastInteraction: new Date().toISOString().slice(0, 10),
    topics: ['pilot scope', 'executive sponsor'],
  },
]

const normalizeContactsResponse = (data?: ContactsResponse): ContactsResponse => {
  const contacts = data?.contacts?.filter((c) => c.contactEmail && c.contactName) ?? []
  if (contacts.length > 0) return { ...data, contacts }
  return {
    contacts: demoContacts,
    source: data?.source ?? 'demo',
    warning: data?.warning ?? data?.error ?? 'Showing demo contacts — no stored contacts found yet.',
  }
}

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
  ingestingEmails: boolean
  minimized: boolean
  graphData: GraphData
  graphLoading: boolean
  depStatus: SidecarStatus_Deps | null
  setRecording: (value: boolean) => void
  setSidecarStatus: (value: RapportState['sidecarStatus']) => void
  setCommandOpen: (value: boolean) => void
  setSettingsOpen: (value: boolean) => void
  setActiveBrief: (brief: Brief | null) => void
  setBriefLoading: (loading: boolean) => void
  setMinimized: (value: boolean) => void
  pushTranscript: (line: string) => void
  setDetectedContacts: (contacts: string[]) => void
  setSelectedContact: (contact: Contact) => void
  fetchContacts: () => Promise<void>
  fetchGraph: () => Promise<void>
  fetchDepStatus: () => Promise<void>
  ingestEmails: () => Promise<void>
  ingestImap: (cfg: { host: string; port: number; username: string; password: string; since_days: number }) => Promise<{ count: number }>
  startRecording: (contact: Contact) => Promise<{ status: string; reason?: string }>
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
  ingestingEmails: false,
  graphData: { nodes: [], edges: [] },
  graphLoading: false,
  depStatus: null,

  setRecording: (value) => set({ isRecording: value }),
  setSidecarStatus: (value) => set({ sidecarStatus: value }),
  setCommandOpen: (value) => set({ commandOpen: value }),
  setSettingsOpen: (value) => set({ settingsOpen: value }),
  setActiveBrief: (brief) => set({ activeBrief: brief }),
  setBriefLoading: (loading) => set({ briefLoading: loading }),
  setMinimized: (value) => set({ minimized: value }),
  pushTranscript: (line) =>
    set((state) => ({ liveTranscript: [...state.liveTranscript.slice(-7), line] })),
  setDetectedContacts: (contacts) => set({ detectedContacts: contacts }),
  setSelectedContact: (contact) => set({ selectedContact: contact }),

  fetchContacts: async () => {
    set({ contactsLoading: true, contactsError: null })
    try {
      const data = await sidecarRequest<ContactsResponse>('/contacts')
      const normalized = normalizeContactsResponse(data)
      const list = normalized.contacts ?? demoContacts
      set({
        contacts: list,
        contactsLoading: false,
        contactsSource: normalized.source ?? null,
        contactsError: normalized.error ?? normalized.warning ?? null,
        selectedContact: list.length > 0 ? list[0] : defaultContact,
      })
    } catch (err) {
      set({
        contacts: demoContacts,
        contactsLoading: false,
        contactsSource: 'demo',
        contactsError: `Could not reach sidecar. Showing demo contacts. ${String(err)}`,
        selectedContact: demoContacts[0],
      })
    }
  },

  fetchGraph: async () => {
    set({ graphLoading: true })
    try {
      const data = await sidecarRequest<GraphData>('/graph')
      set({ graphData: data, graphLoading: false })
    } catch {
      set({ graphLoading: false })
    }
  },

  fetchDepStatus: async () => {
    try {
      const data = await sidecarRequest<SidecarStatus_Deps>('/status')
      set({ depStatus: data })
    } catch {
      /* sidecar offline — leave depStatus null */
    }
  },

  ingestImap: async (cfg) => {
    const data = await sidecarRequest<{ count: number; status: string }>('/ingest/imap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    })
    return { count: data.count ?? 0 }
  },

  ingestEmails: async () => {
    set({ ingestingEmails: true })
    try {
      await sidecarRequest('/ingest/emails', { method: 'POST' })
      await get().fetchContacts()
    } catch {
      /* surfaced via WS error events */
    } finally {
      set({ ingestingEmails: false })
    }
  },

  startRecording: async (contact) => {
    const result = await sidecarRequest<{ status: string; reason?: string }>('/recording/start', {
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
