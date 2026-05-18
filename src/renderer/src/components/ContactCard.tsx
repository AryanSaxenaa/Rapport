import { Building2, MessageSquareText } from 'lucide-react'
import type { Stance } from '../store/rapport-store'

type Contact = {
  contactEmail: string
  contactName: string
  company: string
  stance: Stance
}

export function ContactCard({ contact }: { contact: Contact }) {
  return (
    <section className="contact-card">
      <div className="avatar-mark">{contact.contactName.split(' ').map((part) => part[0]).join('')}</div>
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
      </div>
      <span className={`stance-badge ${contact.stance}`}>{contact.stance}</span>
    </section>
  )
}
