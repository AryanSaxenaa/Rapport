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
  setRecording: (value: boolean) => void
  setSidecarStatus: (value: RapportState['sidecarStatus']) => void
  setCommandOpen: (value: boolean) => void
  setActiveBrief: (brief: Brief | null) => void
  setBriefLoading: (loading: boolean) => void
  pushTranscript: (line: string) => void
  setDetectedContacts: (contacts: string[]) => void
  setSelectedContact: (contact: Contact) => void
  fetchContacts: () => Promise<void>
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
  activeBrief: null,
  briefLoading: false,
  liveTranscript: ['Waiting for meeting audio.', 'Relationship signals will appear here as Rapport listens.'],
  detectedContacts: [],
  selectedContact: defaultContact,
  contacts: [],
  contactsLoading: false,
  contactsError: null,

  setRecording: (value) => set({ isRecording: value }),
  setSidecarStatus: (value) => set({ sidecarStatus: value }),
  setCommandOpen: (value) => set({ commandOpen: value }),
  setActiveBrief: (brief) => set({ activeBrief: brief }),
  setBriefLoading: (loading) => set({ briefLoading: loading }),
  pushTranscript: (line) =>
    set((state) => ({
      liveTranscript: [...state.liveTranscript.slice(-7), line],
    })),
  setDetectedContacts: (contacts) => set({ detectedContacts: contacts }),
  setSelectedContact: (contact) => set({ selectedContact: contact }),

  fetchContacts: async () => {
    set({ contactsLoading: true, contactsError: null })
    try {
      const data = await window.electron?.getContacts?.()
      const list: Contact[] = data?.contacts ?? []
      set({
        contacts: list,
        contactsLoading: false,
        selectedContact: list.length > 0 ? list[0] : defaultContact,
      })
    } catch (err) {
      set({ contactsLoading: false, contactsError: String(err) })
    }
  },

  fetchBrief: async (contactEmail, contactName, company) => {
    set({ briefLoading: true })
    try {
      const brief = await window.electron?.getBrief?.({ contactEmail, contactName, company })
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
