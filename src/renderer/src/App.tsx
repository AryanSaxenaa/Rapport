import { useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Database, Mail, Radio, ShieldCheck } from 'lucide-react'
import { CommandBar } from './components/CommandBar'
import { ContactCard } from './components/ContactCard'
import { FloatingOrb } from './components/FloatingOrb'
import { RelationshipGraph } from './components/RelationshipGraph'
import { demoBrief, useRapportStore } from './store/rapport-store'

export function App() {
  const {
    commandOpen,
    isRecording,
    sidecarStatus,
    selectedContact,
    setCommandOpen,
    setSidecarStatus,
    setActiveBrief,
    pushTranscript
  } = useRapportStore()

  useEffect(() => {
    const cleanup = window.electron?.onToggleCommandBar?.(() => setCommandOpen(!commandOpen))
    return cleanup
  }, [commandOpen, setCommandOpen])

  useEffect(() => {
    const ws = new WebSocket('ws://127.0.0.1:8765/ws/transcript')
    ws.onopen = () => setSidecarStatus('online')
    ws.onerror = () => setSidecarStatus('offline')
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data)
      if (payload.type === 'transcript') pushTranscript(payload.text)
      if (payload.type === 'brief') setActiveBrief(payload.data)
    }
    return () => ws.close()
  }, [pushTranscript, setActiveBrief, setSidecarStatus])

  const nodes = [
    { id: 'northstar', name: 'Northstar', company: 'Northstar Ledger', stance: 'neutral', type: 'company' as const },
    { id: 'mira', name: 'Mira Voss', company: 'Northstar Ledger', stance: 'skeptic', type: 'person' as const },
    { id: 'priya', name: 'Priya Anand', company: 'Northstar Ledger', stance: 'neutral', type: 'person' as const },
    { id: 'owen', name: 'Owen Keller', company: 'Northstar Ledger', stance: 'blocker', type: 'person' as const },
    { id: 'security', name: 'Security', company: 'Risk', stance: 'neutral', type: 'topic' as const }
  ]

  const links = [
    { source: 'northstar', target: 'mira', type: 'owns', strength: 1 },
    { source: 'mira', target: 'priya', type: 'depends', strength: 0.8 },
    { source: 'priya', target: 'security', type: 'reviews', strength: 0.9 },
    { source: 'owen', target: 'mira', type: 'budget', strength: 0.7 }
  ]

  return (
    <main className="rapport-shell">
      <div className="dot-field" />
      <section className="control-surface">
        <header className="topbar">
          <div>
            <span className="glyph">RAPPORT</span>
            <h1>Relationship signal</h1>
          </div>
          <div className={`status-pill ${sidecarStatus}`}>
            <Activity size={14} />
            {sidecarStatus}
          </div>
        </header>

        <div className="scan-line" />

        <div className="overview-grid">
          <ContactCard contact={selectedContact} />
          <section className="signal-panel">
            <div className="panel-heading">
              <Radio size={15} />
              <span>Live capture</span>
            </div>
            <p className="panel-copy">
              {isRecording
                ? 'Listening for stance shifts, commitments, and political context.'
                : 'Start a call capture or generate a brief from known context.'}
            </p>
            <div className="action-row">
              <button
                className="primary-action"
                onClick={async () => {
                  await window.electron?.startRecording?.(selectedContact)
                  useRapportStore.getState().setRecording(true)
                }}
              >
                <Radio size={15} />
                Record
              </button>
              <button
                className="secondary-action"
                onClick={async () => {
                  await window.electron?.stopRecording?.()
                  useRapportStore.getState().setRecording(false)
                }}
              >
                Stop
              </button>
            </div>
          </section>
        </div>

        <section className="brief-strip">
          <div>
            <span className="micro-label">Next useful move</span>
            <p>Open with security controls, then ask who signs procurement before Q3 closes.</p>
          </div>
          <button className="icon-action" onClick={() => setActiveBrief(demoBrief)} title="Show brief">
            <ShieldCheck size={18} />
          </button>
        </section>

        <RelationshipGraph nodes={nodes} links={links} />

        <footer className="footer-actions">
          <button onClick={() => void window.electron?.ingestEmails?.()}>
            <Mail size={14} />
            Ingest email
          </button>
          <button onClick={() => setCommandOpen(true)}>
            <Database size={14} />
            Query memory
          </button>
        </footer>
      </section>

      <FloatingOrb />

      <AnimatePresence>
        {commandOpen && (
          <motion.div
            className="command-layer"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
          >
            <CommandBar onClose={() => setCommandOpen(false)} />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}
