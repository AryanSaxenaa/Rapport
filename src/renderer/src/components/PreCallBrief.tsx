import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Clock, X } from 'lucide-react'
import type { Brief } from '../store/rapport-store'

export function PreCallBrief({ brief, onDismiss }: { brief: Brief; onDismiss: () => void }) {
  return (
    <motion.article
      className="brief-panel"
      initial={{ opacity: 0, y: 48, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 48, scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 140, damping: 24 }}
    >
      <header className="brief-header">
        <div>
          <span className="glyph">PRE-CALL BRIEF</span>
          <h2>{brief.contactName}</h2>
          <p>{brief.company}</p>
        </div>
        <button onClick={onDismiss} title="Dismiss brief">
          <X size={17} />
        </button>
      </header>

      <div className="brief-body">
        <div className={`stance-badge ${brief.currentStance}`}>{brief.currentStance}</div>
        {brief.stanceShiftNote && <p className="stance-note">{brief.stanceShiftNote}</p>}

        <section>
          <h3>
            <AlertTriangle size={14} />
            Concerns
          </h3>
          {brief.topConcerns.map((concern) => (
            <p className="brief-line" key={concern}>{concern}</p>
          ))}
        </section>

        <section>
          <h3>
            <CheckCircle2 size={14} />
            Talking points
          </h3>
          {brief.talkingPoints.map((point) => (
            <p className="brief-line" key={point}>{point}</p>
          ))}
        </section>

        <section>
          <h3>
            <Clock size={14} />
            Context
          </h3>
          <p className="brief-copy">{brief.communicationStyle}</p>
          <p className="brief-copy">{brief.lastInteraction}</p>
          <p className="brief-copy accent-copy">{brief.powerNote}</p>
        </section>
      </div>
    </motion.article>
  )
}
