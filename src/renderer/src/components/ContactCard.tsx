import { motion } from 'framer-motion'
import { Building2, CalendarDays, MessageSquareText } from 'lucide-react'
import type { Contact } from '../store/rapport-store'

export function ContactCard({ contact }: { contact: Contact }) {
  const initials = contact.contactName
    .split(' ')
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <motion.section
      className="contact-card"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="avatar-mark">{initials}</div>
      <div>
        <span className="micro-label">Primary contact</span>
        <h2>{contact.contactName}</h2>
        <p>
          <Building2 size={13} />
          {contact.company}
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
      </div>
      <span className={`stance-badge ${contact.stance}`}>{contact.stance}</span>
    </motion.section>
  )
}
