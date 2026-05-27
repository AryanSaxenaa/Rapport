import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Database, Radio, RefreshCw, Settings, Upload, Users } from 'lucide-react'
import { CommandBar } from './components/CommandBar'
import { ContactCard } from './components/ContactCard'
import { FirstRunWizard } from './components/FirstRunWizard'
import { FloatingOrb } from './components/FloatingOrb'
import { RelationshipGraph } from './components/RelationshipGraph'
import { SettingsPanel } from './components/SettingsPanel'
import { useSidecarSocket } from './hooks/useSidecarSocket'
import { useRapportStore } from './store/rapport-store'
import type { Contact, Brief } from './store/rapport-store'

export function App() {
  const {
    commandOpen,
    settingsOpen,
    minimized,
    isRecording,
    sidecarStatus,
    selectedContact,
    contacts,
    contactsLoading,
    contactsError,
    contactsSource,
    graphData,
    depStatus,
    setCommandOpen,
    setSettingsOpen,
    setSidecarStatus,
    setActiveBrief,
    pushTranscript,
    fetchContacts,
    fetchGraph,
    fetchDepStatus,
    setSelectedContact,
    startRecording,
    stopRecording,
  } = useRapportStore()

  const [wizardDismissed, setWizardDismissed] = useState(false)

  const [dragOver, setDragOver] = useState(false)
  const [fileIngestStatus, setFileIngestStatus] = useState<string | null>(null)

  useSidecarSocket({
    onStatusChange: setSidecarStatus,
    onConnect: () => { void fetchContacts(); void fetchGraph(); void fetchDepStatus() },
    onTranscript: pushTranscript,
    onBrief: (data) => setActiveBrief(data as Brief),
    onError: (msg) => pushTranscript(`Error: ${msg}`),
  })

  useEffect(() => {
    void fetchContacts()
    void fetchGraph()
    void fetchDepStatus()
  }, [fetchContacts, fetchGraph, fetchDepStatus])

  const showWizard =
    !wizardDismissed &&
    sidecarStatus === 'online' &&
    depStatus !== null &&
    (!depStatus.hydradb.ok || !depStatus.openrouter.ok)

  async function ingestFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList).filter(
      (f) => f.name.endsWith('.eml') || f.name.endsWith('.mbox')
    )
    if (files.length === 0) {
      return 0
    }
    let total = 0
    for (const file of files) {
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch('http://127.0.0.1:8765/ingest/file', { method: 'POST', body: form })
        const data = await res.json() as { count?: number }
        total += data.count ?? 0
      } catch {
        throw new Error('Ingest failed — is the sidecar running?')
      }
    }
    return total
  }

  async function handleFileDrop(event: React.DragEvent<HTMLElement>) {
    event.preventDefault()
    setDragOver(false)
    if (Array.from(event.dataTransfer.files).filter((f) => f.name.endsWith('.eml') || f.name.endsWith('.mbox')).length === 0) {
      setFileIngestStatus('Only .eml and .mbox files are supported.')
      return
    }
    try {
      setFileIngestStatus(`Ingesting files…`)
      const total = await ingestFiles(event.dataTransfer.files)
      setFileIngestStatus(`Queued ${total} email${total !== 1 ? 's' : ''} for extraction.`)
      setTimeout(() => setFileIngestStatus(null), 4000)
      void fetchContacts()
      void fetchGraph()
    } catch (err) {
      setFileIngestStatus(err instanceof Error ? err.message : 'Ingest failed.')
    }
  }

  return (
    <main
      className={`rapport-shell${minimized ? ' minimised' : ''}${dragOver ? ' drag-over' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => void handleFileDrop(e)}
    >
      <div className="dot-field" />
      {!minimized && <section className="control-surface">
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

        {contactsSource && (
          <div className={`data-banner ${contactsError ? 'warn' : ''}`}>
            <span>{contactsSource ? `Source: ${contactsSource}` : 'Source: unknown'}</span>
            {contactsError && <span>{contactsError}</span>}
          </div>
        )}

        {contactsLoading ? (
          <div className="loading-drawer">
            <RefreshCw size={16} className="spin" />
            <span>Loading contacts…</span>
          </div>
        ) : contacts.length > 0 ? (
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
                ? 'Listening for stance shifts and commitments.'
                : 'Start a call capture or generate a brief.'}
            </p>
            <div className="action-row">
              <motion.button
                className="primary-action"
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={async () => {
                  const result = await startRecording(selectedContact)
                  if (result.status === 'disabled') {
                    useRapportStore.getState().pushTranscript(`Recording unavailable: ${result.reason ?? 'unknown reason'}`)
                  }
                }}
              >
                <Radio size={15} />
                Start
              </motion.button>
              <motion.button
                className="secondary-action"
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => void stopRecording()}
              >
                End
              </motion.button>
            </div>
          </section>
        </div>

        <RelationshipGraph nodes={graphData.nodes} edges={graphData.edges} />

        {fileIngestStatus && (
          <div className={`data-banner${fileIngestStatus.includes('failed') || fileIngestStatus.includes('supported') ? ' warn' : ''}`}>
            <span>{fileIngestStatus}</span>
          </div>
        )}

        {dragOver && (
          <div className="drop-overlay">
            <Upload size={24} />
            <span>Drop .eml or .mbox to ingest</span>
          </div>
        )}

        <footer className="footer-actions">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => {
              const input = document.createElement('input')
              input.type = 'file'
              input.accept = '.eml,.mbox'
              input.multiple = true
              input.onchange = async () => {
                if (!input.files?.length) return
                try {
                  setFileIngestStatus('Ingesting files…')
                  const total = await ingestFiles(input.files)
                  setFileIngestStatus(`Queued ${total} email${total !== 1 ? 's' : ''} for extraction.`)
                  setTimeout(() => setFileIngestStatus(null), 4000)
                  void fetchContacts()
                  void fetchGraph()
                } catch (err) {
                  setFileIngestStatus(err instanceof Error ? err.message : 'Ingest failed.')
                }
              }
              input.click()
            }}
            title="Import .eml or .mbox files — no account needed"
          >
            <Upload size={14} />
            <span>Import</span>
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setCommandOpen(true)}
          >
            <Database size={14} />
            <span>Memory</span>
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setSettingsOpen(true)}
          >
            <Settings size={14} />
            <span>Settings</span>
          </motion.button>
        </footer>
      </section>}

      <FloatingOrb />

      {showWizard && depStatus && (
        <FirstRunWizard
          depStatus={depStatus}
          onComplete={() => setWizardDismissed(true)}
        />
      )}

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

      <AnimatePresence>
        {settingsOpen && (
          <motion.div
            className="command-layer"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ type: 'spring', stiffness: 200, damping: 28 }}
          >
            <SettingsPanel onClose={() => setSettingsOpen(false)} />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}
