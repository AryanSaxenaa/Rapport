import { useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle, ExternalLink, Key, Loader2 } from 'lucide-react'
import { useRapportStore } from '../store/rapport-store'
import type { SidecarStatusDeps } from '../store/rapport-store'
import './FirstRunWizard.css'

export function FirstRunWizard({ depStatus, onComplete }: { depStatus: SidecarStatusDeps; onComplete: () => void }) {
  const { configureSidecar } = useRapportStore()

  const needsHydraDB = !depStatus.hydradb.ok
  const needsOpenRouter = !depStatus.openrouter.ok

  const [hydraKey, setHydraKey] = useState('')
  const [hydraTenant, setHydraTenant] = useState('orb')
  const [openrouterKey, setOpenrouterKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  async function handleSave() {
    const keys: Record<string, string> = {}
    if (needsHydraDB && hydraKey.trim()) {
      keys['HYDRA_DB_API_KEY'] = hydraKey.trim()
      if (hydraTenant.trim()) keys['HYDRA_DB_TENANT_ID'] = hydraTenant.trim()
    }
    if (needsOpenRouter && openrouterKey.trim()) {
      keys['OPENROUTER_API_KEY'] = openrouterKey.trim()
    }
    if (Object.keys(keys).length === 0) {
      setError('Enter at least one API key to continue.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await configureSidecar(keys)
      setDone(true)
      setTimeout(onComplete, 1400)
    } catch (err) {
      setError(`Failed to save: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setSaving(false)
    }
  }

  if (done) {
    return (
      <div className="wizard-overlay">
        <motion.div className="wizard-card" initial={{ scale: 0.9 }} animate={{ scale: 1 }}>
          <CheckCircle size={32} style={{ color: 'var(--n-green)', margin: '0 auto 12px' }} />
          <p style={{ textAlign: 'center', color: 'var(--n-green)', fontSize: 11 }}>Keys saved. Starting Rapport…</p>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="wizard-overlay">
      <motion.div
        className="wizard-card"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 180, damping: 22 }}
      >
        <div className="wizard-header">
          <span className="glyph" style={{ fontSize: 13 }}>RAPPORT</span>
          <h2>First-run setup</h2>
          <p>Two API keys are needed to store memory and generate briefs.</p>
        </div>

        <div className="wizard-fields">
          {needsHydraDB && (
            <div className="wizard-field-group">
              <label className="micro-label">
                HydraDB API key
                <a
                  href="https://app.hydradb.com"
                  target="_blank"
                  rel="noreferrer"
                  style={{ marginLeft: 6, color: 'var(--n-dim)' }}
                >
                  <ExternalLink size={10} />
                </a>
              </label>
              <input
                className="settings-input"
                type="password"
                placeholder="hdb-…"
                value={hydraKey}
                onChange={(e) => setHydraKey(e.target.value)}
              />
              <label className="micro-label" style={{ marginTop: 6 }}>Tenant ID (leave "orb" for default)</label>
              <input
                className="settings-input"
                placeholder="orb"
                value={hydraTenant}
                onChange={(e) => setHydraTenant(e.target.value)}
              />
            </div>
          )}

          {needsOpenRouter && (
            <div className="wizard-field-group">
              <label className="micro-label">
                OpenRouter API key
                <a
                  href="https://openrouter.ai/keys"
                  target="_blank"
                  rel="noreferrer"
                  style={{ marginLeft: 6, color: 'var(--n-dim)' }}
                >
                  <ExternalLink size={10} />
                </a>
              </label>
              <input
                className="settings-input"
                type="password"
                placeholder="sk-or-…"
                value={openrouterKey}
                onChange={(e) => setOpenrouterKey(e.target.value)}
              />
            </div>
          )}

          {error && <p className="settings-error">{error}</p>}
        </div>

        <div className="wizard-footer">
          <button
            className="settings-action"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => void handleSave()}
            disabled={saving}
          >
            {saving ? <Loader2 size={13} className="spin" /> : <Key size={13} />}
            {saving ? 'Saving…' : 'Save and continue'}
          </button>

        </div>
      </motion.div>
    </div>
  )
}
