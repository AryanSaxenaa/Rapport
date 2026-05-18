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

type Contact = {
  contactEmail: string
  contactName: string
  company: string
  stance: Stance
}

type RapportState = {
  isRecording: boolean
  sidecarStatus: 'checking' | 'online' | 'offline'
  commandOpen: boolean
  activeBrief: Brief | null
  liveTranscript: string[]
  detectedContacts: string[]
  selectedContact: Contact
  setRecording: (value: boolean) => void
  setSidecarStatus: (value: RapportState['sidecarStatus']) => void
  setCommandOpen: (value: boolean) => void
  setActiveBrief: (brief: Brief | null) => void
  pushTranscript: (line: string) => void
  setDetectedContacts: (contacts: string[]) => void
}

export const demoBrief: Brief = {
  contactName: 'Mira Voss',
  company: 'Northstar Ledger',
  currentStance: 'skeptic',
  stanceShiftNote: 'Moved from neutral after procurement asked for a security review.',
  topConcerns: ['Data retention policy', 'rollout workload for regional directors', 'budget timing before Q3 close'],
  communicationStyle: 'Prefers compact written summaries with exact next steps and named owners.',
  talkingPoints: [
    'Lead with the revised retention controls.',
    'Offer a phased rollout that protects the operations team.',
    'Ask whether Priya still owns the security sign-off.'
  ],
  landmines: ['Do not frame this as a lightweight pilot.', 'Avoid mentioning competitive replacement until she raises it.'],
  lastInteraction: 'Email thread, 2026-05-14: asked for proof that admins can export audit logs.',
  powerNote: 'Priya Anand influences technical approval; Owen Keller controls final budget release.'
}

export const useRapportStore = create<RapportState>((set) => ({
  isRecording: false,
  sidecarStatus: 'checking',
  commandOpen: false,
  activeBrief: null,
  liveTranscript: [
    'Waiting for meeting audio.',
    'Relationship signals will appear here as Rapport listens.'
  ],
  detectedContacts: ['Mira Voss', 'Priya Anand'],
  selectedContact: {
    contactEmail: 'mira.voss@northstar-ledger.example',
    contactName: 'Mira Voss',
    company: 'Northstar Ledger',
    stance: 'skeptic'
  },
  setRecording: (value) => set({ isRecording: value }),
  setSidecarStatus: (value) => set({ sidecarStatus: value }),
  setCommandOpen: (value) => set({ commandOpen: value }),
  setActiveBrief: (brief) => set({ activeBrief: brief }),
  pushTranscript: (line) =>
    set((state) => ({
      liveTranscript: [...state.liveTranscript.slice(-7), line]
    })),
  setDetectedContacts: (contacts) => set({ detectedContacts: contacts })
}))
