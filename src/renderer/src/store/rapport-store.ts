import { create } from 'zustand'

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
  const contacts = data?.contacts?.filter((contact) => contact.contactEmail && contact.contactName) ?? []
  if (contacts.length > 0) return { ...data, contacts }

  return {
    contacts: demoContacts,
    source: data?.source ?? 'demo',
    warning: data?.warning ?? data?.error ?? 'Showing demo contacts because no stored contacts were returned yet.',
  }
}

const sidecarRequest = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${SIDECAR_URL}${path}`, init)
  if (!response.ok) {
    throw new Error(`Sidecar ${response.status}: ${await response.text()}`)
  }
  return response.json() as Promise<T>
}

const getContacts = async (): Promise<ContactsResponse> => {
  if (window.electron?.getContacts) {
    return window.electron.getContacts()
  }
  return sidecarRequest<ContactsResponse>('/contacts')
}

const ingestEmails = async (): Promise<unknown> => {
  if (window.electron?.ingestEmails) {
    return window.electron.ingestEmails()
  }
  return sidecarRequest('/ingest/emails', { method: 'POST' })
}

const getBrief = async (payload: { contactEmail: string; contactName: string; company: string }): Promise<Brief> => {
  if (window.electron?.getBrief) {
    return window.electron.getBrief(payload)
  }
  const params = new URLSearchParams({
    contact_name: payload.contactName,
    company: payload.company,
  })
  return sidecarRequest<Brief>(`/brief/${encodeURIComponent(payload.contactEmail)}?${params}`)
}

type RapportState = {
  isRecording: boolean
  sidecarStatus: 'checking' | 'online' | 'offline'
  commandOpen: boolean
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
  setRecording: (value: boolean) => void
  setSidecarStatus: (value: RapportState['sidecarStatus']) => void
  setCommandOpen: (value: boolean) => void
  setActiveBrief: (brief: Brief | null) => void
  setBriefLoading: (loading: boolean) => void
  setMinimized: (value: boolean) => void
  pushTranscript: (line: string) => void
  setDetectedContacts: (contacts: string[]) => void
  setSelectedContact: (contact: Contact) => void
  fetchContacts: () => Promise<void>
  ingestEmails: () => Promise<void>
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

  setRecording: (value) => set({ isRecording: value }),
  setSidecarStatus: (value) => set({ sidecarStatus: value }),
  setCommandOpen: (value) => set({ commandOpen: value }),
  setActiveBrief: (brief) => set({ activeBrief: brief }),
  setBriefLoading: (loading) => set({ briefLoading: loading }),
  setMinimized: (value) => set({ minimized: value }),
  pushTranscript: (line) =>
    set((state) => ({
      liveTranscript: [...state.liveTranscript.slice(-7), line],
    })),
  setDetectedContacts: (contacts) => set({ detectedContacts: contacts }),
  setSelectedContact: (contact) => set({ selectedContact: contact }),

  fetchContacts: async () => {
    set({ contactsLoading: true, contactsError: null })
    try {
      const data = await getContacts()
      const normalized = normalizeContactsResponse(data)
      const list: Contact[] = normalized.contacts ?? demoContacts
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

  ingestEmails: async () => {
    set({ ingestingEmails: true })
    try {
      await ingestEmails()
      // Refresh contacts immediately (endpoint returns what's available)
      await get().fetchContacts()
    } catch {
      /* ingest errors are surfaced silently */
    } finally {
      set({ ingestingEmails: false })
    }
  },

  fetchBrief: async (contactEmail, contactName, company) => {
    set({ briefLoading: true })
    try {
      const brief = await getBrief({ contactEmail, contactName, company })
      if (brief) {
        set({ activeBrief: brief, briefLoading: false })
        return brief
      }
      set({ briefLoading: false })
      return null
    } catch {
      set({ briefLoading: false })
      return null
    }
  },
}))
