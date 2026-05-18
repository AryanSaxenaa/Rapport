import { useEffect, useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Database, Mail, Radio, RefreshCw, Users } from 'lucide-react'
import { CommandBar } from './components/CommandBar'
import { ContactCard } from './components/ContactCard'
import { FloatingOrb } from './components/FloatingOrb'
import { RelationshipGraph } from './components/RelationshipGraph'
import { useRapportStore } from './store/rapport-store'
import type { Contact } from './store/rapport-store'

export function App() {
  const {
    commandOpen,
    isRecording,
    sidecarStatus,
    selectedContact,
    contacts,
    contactsLoading,
    setCommandOpen,
    setSidecarStatus,
    setActiveBrief,
    pushTranscript,
    fetchContacts,
    setSelectedContact,
  } = useRapportStore()

  // Listen for orb toggle from main process
  useEffect(() => {
    const cleanup = window.electron?.onToggleCommandBar?.(() => {
      const current = useRapportStore.getState().commandOpen
      setCommandOpen(!current)
    })
    return cleanup
  }, [setCommandOpen])

  // Fetch contacts on mount
  useEffect(() => {
    fetchContacts()
  }, [fetchContacts])

  // WebSocket connection
  useEffect(() => {
    const ws = new WebSocket('ws://127.0.0.1:8765/ws/transcript')
    ws.onopen = () => setSidecarStatus('online')
    ws.onerror = () => setSidecarStatus('offline')
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'transcript') pushTranscript(payload.text)
        if (payload.type === 'brief') setActiveBrief(payload.data)
      } catch {
        /* ignore malformed frames */
      }
    }
    return () => ws.close()
  }, [pushTranscript, setActiveBrief, setSidecarStatus])

  // Build graph nodes/links from contacts
  const graphData = useMemo(() => {
    if (contacts.length === 0) return { nodes: [], links: [] }
    const nodes = contacts.map((c, i) => ({
      id: c.contactEmail,
      name: c.contactName,
      company: c.company,
      stance: c.stance,
      type: 'person' as const,
      group: i,
    }))

    const links = []
    for (let i = 0; i < nodes.length - 1; i++) {
      links.push({
        source: nodes[i].id,
        target: nodes[i + 1].id,
        type: 'relates',
        strength: 1,
      })
    }
    return { nodes, links }
  }, [contacts])

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
            <motion.div
              animate={sidecarStatus === 'online' ? { opacity: [1, 0.4, 1] } : {}}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            >
              <Activity size={14} />
            </motion.div>
            {sidecarStatus}
          </div>
        </header>

        <div className="scan-line" />

        {contactsLoading ? (
          <div className="loading-drawer">
            <RefreshCw size={16} className="spin" />
            <span>Loading contacts…</span>
          </div>
        ) : contacts.length > 1 ? (
          <div className="contact-strip">
            <Users size={13} />
            <span className="micro-label">Contacts</span>
            <div className="contact-chips">
              {contacts.map((c: Contact) => (
                <button
                  key={c.contactEmail}
                  className={`contact-chip ${selectedContact.contactEmail === c.contactEmail ? 'active' : ''}`}
                  onClick={() => setSelectedContact(c)}
                >
                  {c.contactName}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="overview-grid">
          {contacts.length > 0 ? (
            <ContactCard contact={selectedContact} />
          ) : (
            <section className="contact-card empty-state">
              <div className="avatar-mark">?</div>
              <div>
                <span className="micro-label">No contacts yet</span>
                <p style={{ marginTop: 10, color: 'var(--n-dim)', fontSize: 11 }}>
                  Ingest emails or start recording to populate your relationship graph.
                </p>
              </div>
            </section>
          )}
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
              <motion.button
                className="primary-action"
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={async () => {
                  await window.electron?.startRecording?.(selectedContact)
                  useRapportStore.getState().setRecording(true)
                }}
              >
                <Radio size={15} />
                Record
              </motion.button>
              <motion.button
                className="secondary-action"
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={async () => {
                  await window.electron?.stopRecording?.()
                  useRapportStore.getState().setRecording(false)
                }}
              >
                Stop
              </motion.button>
            </div>
          </section>
        </div>

        <RelationshipGraph nodes={graphData.nodes} links={graphData.links} />

        <footer className="footer-actions">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => void window.electron?.ingestEmails?.()}
          >
            <Mail size={14} />
            <span>Ingest email</span>
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setCommandOpen(true)}
          >
            <Database size={14} />
            <span>Query memory</span>
          </motion.button>
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
            transition={{ type: 'spring', stiffness: 200, damping: 28 }}
          >
            <CommandBar onClose={() => setCommandOpen(false)} />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}
