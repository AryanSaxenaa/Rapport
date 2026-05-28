import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { CheckCircle, Database, Mic, RefreshCw, Server, Trash2, Wifi, X } from 'lucide-react'
import { SIDECAR_URL, useRapportStore } from '../store/rapport-store'
import type { SidecarStatusDeps } from '../store/rapport-store'

const DEP_ICONS: Record<string, ReactNode> = {
  hydradb: <Database size={12} />,
  openrouter: <Server size={12} />,
  microphone: <Mic size={12} />,
  imap: <Wifi size={12} />,
}

const DEP_LABELS: Record<string, string> = {
  hydradb: 'HydraDB',
  openrouter: 'OpenRouter',
  microphone: 'Microphone',
  imap: 'IMAP / Email',
}

export function SettingsPanel({ onClose }: { onClose: () => void }) {
  const { depStatus, fetchDepStatus, ingestImap, fetchContacts, fetchGraph } = useRapportStore()

  const [host, setHost] = useState('')
  const [port, setPort] = useState('993')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [sinceDays, setSinceDays] = useState('90')
  const [imapStatus, setImapStatus] = useState<string | null>(null)
  const [imapError, setImapError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)

  const [deleteStatus, setDeleteStatus] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    void fetchDepStatus()
  }, [fetchDepStatus])

  async function handleImapSync() {
    if (!host || !username || !password) {
      setImapError('Host, username, and password are required.')
      return
    }
    setSyncing(true)
    setImapError(null)
    setImapStatus(null)
    try {
      const result = await ingestImap({
        host,
        port: parseInt(port) || 993,
        username,
        password,
        since_days: parseInt(sinceDays) || 90,
      })
      setImapStatus(`Queued ${result.count} email${result.count !== 1 ? 's' : ''} for extraction.`)
      void fetchContacts()
      void fetchGraph()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setImapError(msg.includes('401') ? 'Authentication failed — check your app password.' : `Sync failed: ${msg}`)
    } finally {
      setSyncing(false)
    }
  }

  async function handleDeleteData(endpoint: string, label: string) {
    setDeleteStatus(null)
    setDeleteError(null)
    try {
      const res = await fetch(`${SIDECAR_URL}${endpoint}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setDeleteStatus(`${label} deleted.`)
      void fetchContacts()
      void fetchGraph()
    } catch (err: unknown) {
      setDeleteError(`Failed to delete ${label}: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  return (
    <section className="settings-panel">
      <div className="settings-header">
        <span className="micro-label">SETTINGS</span>
        <button className="settings-close" onClick={onClose}><X size={14} /></button>
      </div>

      <div className="settings-section">
        <span className="micro-label">Dependency status</span>
        {!depStatus ? (
          <p className="settings-dim">Sidecar offline or unreachable.</p>
        ) : (
          <div className="dep-status-list">
            {(Object.keys(DEP_LABELS) as Array<keyof SidecarStatusDeps>).map((key) => {
              const dep = depStatus[key]
              return (
                <div key={key} className="dep-row">
                  <span className="dep-icon">{DEP_ICONS[key]}</span>
                  <span className="dep-label">{DEP_LABELS[key]}</span>
                  <span className={`dep-dot ${dep.ok ? 'ok' : 'fail'}`} />
                  {!dep.ok && dep.reason && (
                    <span className="dep-reason">{dep.reason}</span>
                  )}
                </div>
              )
            })}
          </div>
        )}
        <button className="settings-refresh" onClick={() => void fetchDepStatus()}>
          <RefreshCw size={11} /> Refresh
        </button>
      </div>

      <div className="settings-section">
        <span className="micro-label">IMAP sync</span>
        <p className="settings-dim">Sync emails without Google OAuth. Use an app password, not your main password.</p>
        <div className="imap-form">
          <input
            className="settings-input"
            placeholder="imap.gmail.com"
            value={host}
            onChange={(e) => setHost(e.target.value)}
          />
          <div className="imap-row-2">
            <input
              className="settings-input"
              placeholder="Port (993)"
              value={port}
              onChange={(e) => setPort(e.target.value)}
              style={{ width: 80 }}
            />
            <input
              className="settings-input"
              placeholder="Days back (90)"
              value={sinceDays}
              onChange={(e) => setSinceDays(e.target.value)}
              style={{ width: 110 }}
            />
          </div>
          <input
            className="settings-input"
            placeholder="username@gmail.com"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            className="settings-input"
            type="password"
            placeholder="App password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {imapError && <p className="settings-error">{imapError}</p>}
          {imapStatus && (
            <p className="settings-ok">
              <CheckCircle size={11} /> {imapStatus}
            </p>
          )}
          <button
            className="settings-action"
            onClick={() => void handleImapSync()}
            disabled={syncing}
          >
            {syncing ? <RefreshCw size={12} className="spin" /> : <Wifi size={12} />}
            {syncing ? 'Connecting...' : 'Sync inbox'}
          </button>
        </div>
      </div>

      <div className="settings-section">
        <span className="micro-label">Data retention</span>
        <p className="settings-dim">Delete locally stored data. This does not affect data stored in HydraDB.</p>
        {deleteStatus && (
          <p className="settings-ok">
            <CheckCircle size={11} /> {deleteStatus}
          </p>
        )}
        {deleteError && <p className="settings-error">{deleteError}</p>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button
            className="settings-action"
            style={{ background: 'rgba(255, 80, 80, 0.15)', color: '#ff6b6b' }}
            onClick={() => void handleDeleteData('/data/contacts', 'Local contacts')}
          >
            <Trash2 size={12} /> Delete local contacts
          </button>
          <button
            className="settings-action"
            style={{ background: 'rgba(255, 80, 80, 0.15)', color: '#ff6b6b' }}
            onClick={() => void handleDeleteData('/data/all', 'All local data')}
          >
            <Trash2 size={12} /> Delete all local data
          </button>
        </div>
      </div>
    </section>
  )
}
