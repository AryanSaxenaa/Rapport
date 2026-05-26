import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Database, Mail, Radio, RefreshCw, Upload, Users } from 'lucide-react'
import { CommandBar } from './components/CommandBar'
import { ContactCard } from './components/ContactCard'
import { FloatingOrb } from './components/FloatingOrb'
import { RelationshipGraph } from './components/RelationshipGraph'
import { useRapportStore } from './store/rapport-store'
import type { Contact } from './store/rapport-store'

export function App() {
  const {
    commandOpen,
    minimized,
    isRecording,
    sidecarStatus,
    selectedContact,
    contacts,
    contactsLoading,
    contactsError,
    contactsSource,
    ingestingEmails,
    setCommandOpen,
    setSidecarStatus,
    setActiveBrief,
    pushTranscript,
    fetchContacts,
    setSelectedContact,
    ingestEmails,
  } = useRapportStore()

  const [dragOver, setDragOver] = useState(false)
  const [fileIngestStatus, setFileIngestStatus] = useState<string | null>(null)

  // WebSocket connection with auto-reconnect
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const connectWebSocket = useCallback(() => {
    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    try {
      const ws = new WebSocket('ws://127.0.0.1:8765/ws/transcript')
      wsRef.current = ws

      ws.onopen = () => {
        setSidecarStatus('online')
        // Refresh contacts when we reconnect
        fetchContacts()
        // Clear any reconnect timer since we're connected
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = null
        }
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'transcript') pushTranscript(payload.text)
          if (payload.type === 'brief') setActiveBrief(payload.data)
        } catch {
          /* ignore malformed frames */
        }
      }

      ws.onerror = () => {
        setSidecarStatus('offline')
      }

      ws.onclose = () => {
        setSidecarStatus('offline')
        wsRef.current = null
        // Schedule reconnect
        if (!reconnectTimer.current) {
          reconnectTimer.current = setTimeout(() => {
            reconnectTimer.current = null
            connectWebSocket()
          }, 3000)
        }
      }
    } catch {
      setSidecarStatus('offline')
      // Schedule reconnect on error too
      if (!reconnectTimer.current) {
        reconnectTimer.current = setTimeout(() => {
          reconnectTimer.current = null
          connectWebSocket()
        }, 3000)
      }
    }
  }, [fetchContacts, pushTranscript, setActiveBrief, setSidecarStatus])

  useEffect(() => {
    connectWebSocket()
    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connectWebSocket])

  useEffect(() => {
    void fetchContacts()
  }, [fetchContacts])

  // Build graph nodes only — edges come from /graph endpoint (semantic, evidence-backed)
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
    return { nodes, links: [] }
  }, [contacts])

  async function handleFileDrop(event: React.DragEvent<HTMLElement>) {
    event.preventDefault()
    setDragOver(false)
    const files = Array.from(event.dataTransfer.files).filter(
      (f) => f.name.endsWith('.eml') || f.name.endsWith('.mbox')
    )
    if (files.length === 0) {
      setFileIngestStatus('Only .eml and .mbox files are supported.')
      return
    }
    setFileIngestStatus(`Ingesting ${files.length} file${files.length > 1 ? 's' : ''}…`)
    let total = 0
    for (const file of files) {
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch('http://127.0.0.1:8765/ingest/file', { method: 'POST', body: form })
        const data = await res.json() as { count?: number }
        total += data.count ?? 0
      } catch {
        setFileIngestStatus('Ingest failed — is the sidecar running?')
        return
      }
    }
    setFileIngestStatus(`Queued ${total} email${total !== 1 ? 's' : ''} for extraction.`)
    setTimeout(() => setFileIngestStatus(null), 4000)
    void fetchContacts()
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
                  await window.electron?.startRecording?.(selectedContact)
                  useRapportStore.getState().setRecording(true)
                }}
              >
                <Radio size={15} />
                Start
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
                End
              </motion.button>
            </div>
          </section>
        </div>

        <RelationshipGraph nodes={graphData.nodes} links={graphData.links} />

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
            disabled={ingestingEmails}
            onClick={() => void ingestEmails()}
            style={{ opacity: ingestingEmails ? 0.6 : 1 }}
            title="Ingest via Gmail OAuth (requires credentials.json)"
          >
            {ingestingEmails ? <RefreshCw size={14} className="spin" /> : <Mail size={14} />}
            <span>{ingestingEmails ? 'Ingesting…' : 'Ingest'}</span>
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => {
              const input = document.createElement('input')
              input.type = 'file'
              input.accept = '.eml,.mbox'
              input.multiple = true
              input.onchange = async () => {
                const files = Array.from(input.files ?? [])
                if (!files.length) return
                setFileIngestStatus(`Ingesting ${files.length} file${files.length > 1 ? 's' : ''}…`)
                let total = 0
                for (const file of files) {
                  const form = new FormData()
                  form.append('file', file)
                  try {
                    const res = await fetch('http://127.0.0.1:8765/ingest/file', { method: 'POST', body: form })
                    const data = await res.json() as { count?: number }
                    total += data.count ?? 0
                  } catch {
                    setFileIngestStatus('Ingest failed — is the sidecar running?')
                    return
                  }
                }
                setFileIngestStatus(`Queued ${total} email${total !== 1 ? 's' : ''} for extraction.`)
                setTimeout(() => setFileIngestStatus(null), 4000)
                void fetchContacts()
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
        </footer>
      </section>}

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
