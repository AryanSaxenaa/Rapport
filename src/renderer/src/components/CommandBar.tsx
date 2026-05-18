import { useState } from 'react'
import { Loader2, Search, X } from 'lucide-react'
import { demoBrief, useRapportStore } from '../store/rapport-store'

export function CommandBar({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState('brief for mira.voss@northstar-ledger.example')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { selectedContact, setActiveBrief } = useRapportStore()

  async function runCommand() {
    setLoading(true)
    setError(null)
    try {
      if (query.toLowerCase().includes('brief')) {
        const brief = await window.electron?.getBrief?.({
          contactEmail: selectedContact.contactEmail,
          contactName: selectedContact.contactName,
          company: selectedContact.company
        })
        setActiveBrief(brief ?? demoBrief)
        onClose()
        return
      }
      setError('Try “brief for mira” or use the email ingest action.')
    } catch {
      setActiveBrief(demoBrief)
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="command-bar">
      <div className="command-input-wrap">
        <Search size={18} />
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') void runCommand()
            if (event.key === 'Escape') onClose()
          }}
        />
        <button onClick={onClose} title="Close command bar">
          <X size={16} />
        </button>
      </div>
      {error && <p className="command-error">{error}</p>}
      <button className="command-submit" onClick={() => void runCommand()} disabled={loading}>
        {loading ? <Loader2 size={15} className="spin" /> : null}
        Run
      </button>
    </section>
  )
}
