import { useState } from 'react'
import { motion } from 'framer-motion'
import { Building2, CalendarDays, MessageSquareText, Zap } from 'lucide-react'
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
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
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

        {briefVisible ? (
          <div className="brief-panel">
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
          </div>
        ) : (
          <button
            className="brief-trigger"
            onClick={() => void loadBrief()}
            disabled={loading || !contact.contactEmail}
          >
            <Zap size={11} />
            {loading ? 'Generating…' : 'Pre-call brief'}
          </button>
        )}
      </div>
      <span className={`stance-badge ${contact.stance}`}>{contact.stance}</span>
    </motion.section>
  )
}
