import { useState } from 'react'
import { Loader2, Search, X } from 'lucide-react'
import { useRapportStore } from '../store/rapport-store'

export function CommandBar({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { selectedContact, setActiveBrief, fetchBrief } = useRapportStore()

  async function runCommand() {
    setLoading(true)
    setError(null)
    try {
      if (query.toLowerCase().includes('brief')) {
        const brief = await fetchBrief(
          selectedContact.contactEmail,
          selectedContact.contactName,
          selectedContact.company
        )
        if (!brief) {
          setError('No brief available — try ingesting emails first or check the sidecar is running.')
          return
        }
        onClose()
        return
      }
      setError('Try "brief for [contact]" or use the email ingest action.')
    } catch {
      setError('Sidecar request failed. Is the Python sidecar running on port 8765?')
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
          placeholder="brief for [email]"
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
