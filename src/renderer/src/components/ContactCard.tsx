import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Building2, CalendarDays, FileText, MessageSquareText, Zap } from 'lucide-react'
import type { Contact, Brief } from '../store/rapport-store'
import { useRapportStore } from '../store/rapport-store'

export function ContactCard({ contact }: { contact: Contact }) {
  const { fetchBrief } = useRapportStore()
  const [brief, setBrief] = useState<Brief | null>(null)
  const [loading, setLoading] = useState(false)
  const [briefContact, setBriefContact] = useState<string | null>(null)

  const initials = contact.contactName
    .split(' ')
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  // BUG-23: Reset loading when the contact prop changes so the button never
  // shows 'Generating…' for a contact that has no active fetch in flight.
  useEffect(() => {
    setLoading(false)
  }, [contact.contactEmail])

  async function loadBrief() {
    if (!contact.contactEmail) return
    setLoading(true)
    const result = await fetchBrief(contact.contactEmail, contact.contactName, contact.company)
    setBrief(result)
    setBriefContact(contact.contactEmail)
    setLoading(false)
  }

  const briefVisible = brief && briefContact === contact.contactEmail

  return (
    <motion.section
      className="contact-card"
      key={contact.contactEmail}
      layout
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, type: 'spring', bounce: 0.2 }}
    >
      <div className="avatar-mark">{initials}</div>
      <div className="contact-card-body">
        <span className="micro-label">Primary contact</span>
        <h2>{contact.contactName}</h2>
        <p>
          <Building2 size={13} />
          {contact.company || '—'}
        </p>
        <p>
          <MessageSquareText size={13} />
          {contact.contactEmail}
        </p>
        {contact.lastInteraction && (
          <p className="interaction-note">
            <CalendarDays size={12} />
            Last: {contact.lastInteraction}
          </p>
        )}
        {contact.topics && contact.topics.length > 0 && (
          <div className="topic-chips">
            {contact.topics.slice(0, 5).map((t) => (
              <span key={t} className="topic-chip">{t}</span>
            ))}
          </div>
        )}
        {contact.summary && (
          <p className="interaction-note">
            {/* BUG-28: FileText is semantically correct for a summary; CalendarDays was copy-pasted from the lastInteraction block above */}
            <FileText size={12} />
            {contact.summary}
          </p>
        )}
        {contact.commitments && contact.commitments.length > 0 && (
          <div className="brief-section">
            <span className="micro-label">Commitments ({contact.commitments.length})</span>
            <ul>
              {contact.commitments.slice(0, 3).map((c, i) => (
                <li key={i}>
                  <strong>{c.owner}:</strong> {c.what}
                  <span className={`commit-status ${c.status}`}>{c.status}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {contact.unresolved && contact.unresolved.length > 0 && (
          <div className="brief-section">
            <span className="micro-label">Awaiting ({contact.unresolved.length})</span>
            <ul>
              {contact.unresolved.slice(0, 3).map((u, i) => (
                <li key={i}>
                  <strong>{u.holder}</strong> awaits {u.awaiting_from}: {u.what}
                </li>
              ))}
            </ul>
          </div>
        )}
        {contact.sentimentShift && (
          <p className="brief-shift-note">{contact.sentimentShift}</p>
        )}

        {briefVisible ? (
          <motion.div
            className="brief-panel"
            layout
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
          >
            {brief.stanceShiftNote && (
              <p className="brief-shift-note">{brief.stanceShiftNote}</p>
            )}
            {brief.topConcerns.length > 0 && (
              <div className="brief-section">
                <span className="micro-label">Top concerns</span>
                <ul>
                  {brief.topConcerns.slice(0, 3).map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
            {brief.talkingPoints.length > 0 && (
              <div className="brief-section">
                <span className="micro-label">Talking points</span>
                <ul>
                  {brief.talkingPoints.slice(0, 2).map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
            {brief.powerNote && (
              <p className="brief-power-note">{brief.powerNote}</p>
            )}
          </motion.div>
        ) : (
          <motion.button
            layout
            className="brief-trigger"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => void loadBrief()}
            disabled={loading || !contact.contactEmail}
          >
            <Zap size={11} />
            {loading ? 'Generating…' : 'Pre-call brief'}
          </motion.button>
        )}
      </div>
      <span className={`stance-badge ${contact.stance}`}>{contact.stance}</span>
    </motion.section>
  )
}
