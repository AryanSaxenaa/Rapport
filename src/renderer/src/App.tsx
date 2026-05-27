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
import { SIDECAR_URL, useRapportStore } from './store/rapport-store'
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

  // BUG-22: Previously, fetchContacts/fetchGraph/fetchDepStatus were both called
  // here in a useEffect AND again inside onConnect, causing a double-fetch on
  // every WebSocket connection.  The single source of truth is onConnect: it
  // fires once when the socket first connects (or reconnects), which is exactly
  // when stale data needs refreshing.  The standalone useEffect is removed.
  useSidecarSocket({
    onStatusChange: setSidecarStatus,
    onConnect: () => { void fetchContacts(); void fetchGraph(); void fetchDepStatus() },
    onTranscript: pushTranscript,
    onBrief: (data) => setActiveBrief(data as Brief),
    onError: (msg) => pushTranscript(`Error: ${msg}`),
    // BUG-24: Handle ingest_complete so contacts + graph refresh automatically
    // after any background ingest batch (file, IMAP, or Gmail).
    onIngestComplete: () => { void fetchContacts(); void fetchGraph() },
  })

  // Fallback: if the WebSocket never connects (offline), still attempt to load
  // contacts once on mount via HTTP so the UI isn't completely blank.
  useEffect(() => {
    if (sidecarStatus !== 'online') {
      void fetchContacts()
      void fetchDepStatus()
    }
    // Run only once on mount — intentionally omitting sidecarStatus from deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const showWizard =
    !wizardDismissed &&
    sidecarStatus === 'online' &&
    depStatus !== null &&
    (!depStatus.hydradb.ok || !depStatus.openrouter.ok)

  async function ingestFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList).filter(
      (f) => f.name.endsWith('.eml') || f.name.endsWith('.mbox')
    )
    if (files.length === 0) return 0
    let total = 0
    for (const file of files) {
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch(`${SIDECAR_URL}/ingest/file`, { method: 'POST', body: form })
        // BUG-25: Must check res.ok before calling res.json() — an error
        // response may not be valid JSON, or may be a FastAPI HTML error page.
        if (!res.ok) throw new Error(`Ingest failed: HTTP ${res.status}`)
        const data = await res.json() as { count?: number }
        total += data.count ?? 0
      } catch (err) {
        console.warn(`Rapport: ingest failed for ${file.name}`, err)
      }
    }
    return total
  }

  async function handleFileDrop(event: React.DragEvent<HTMLElement>) {
    event.preventDefault()
    setDragOver(false)
    // BUG-26: The old code performed the file-type check separately and then
    // passed the raw FileList (with any invalid files still in it) to ingestFiles.
    // ingestFiles already filters internally, so we just let it handle everything
    // and only show the 'no valid files' message when the count comes back zero.
    try {
      setFileIngestStatus('Ingesting files…')
      const total = await ingestFiles(event.dataTransfer.files)
      if (total === 0) {
        setFileIngestStatus('Only .eml and .mbox files are supported.')
        return
      }
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
                <motion.button
                  key={c.contactEmail}
                  className={`contact-chip ${selectedContact.contactEmail === c.contactEmail ? 'active' : ''}`}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setSelectedContact(c)}
                >
                  {c.contactName}
                </motion.button>
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
          <motion.section
            className="signal-panel"
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.1, type: 'spring', bounce: 0.2 }}
          >
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
          </motion.section>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2, type: 'spring', bounce: 0.2 }}
        >
          <RelationshipGraph nodes={graphData.nodes} edges={graphData.edges} />
        </motion.div>

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
                  if (total === 0) {
                    setFileIngestStatus('No valid .eml or .mbox emails found in the selected files.')
                    return
                  }
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
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={0.4}
            onDragEnd={(_e, { offset, velocity }) => {
              if (offset.y > 100 || velocity.y > 500) {
                setCommandOpen(false)
              }
            }}
            initial={{ opacity: 0, y: 40, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 350, damping: 30 }}
          >
            <div className="glass-panel" style={{ borderRadius: 8 }}>
              <CommandBar onClose={() => setCommandOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {settingsOpen && (
          <motion.div
            className="command-layer"
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={0.4}
            onDragEnd={(_e, { offset, velocity }) => {
              if (offset.y > 100 || velocity.y > 500) {
                setSettingsOpen(false)
              }
            }}
            initial={{ opacity: 0, y: 40, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 350, damping: 30 }}
          >
            <div className="glass-panel" style={{ borderRadius: 8 }}>
              <SettingsPanel onClose={() => setSettingsOpen(false)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}
