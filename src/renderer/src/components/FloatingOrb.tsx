import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Mic } from 'lucide-react'
import { PreCallBrief } from './PreCallBrief'
import { useRapportStore } from '../store/rapport-store'

type OrbState = 'idle' | 'live' | 'brief'

export function FloatingOrb() {
  const { isRecording, activeBrief, liveTranscript, detectedContacts, setActiveBrief } = useRapportStore()
  const [orbState, setOrbState] = useState<OrbState>('idle')

  useEffect(() => {
    if (activeBrief) setOrbState('brief')
    else if (isRecording) setOrbState('live')
    else setOrbState('idle')
  }, [isRecording, activeBrief])

  return (
    <div className="orb-anchor">
      <AnimatePresence mode="wait">
        {orbState === 'idle' && (
          <motion.button
            key="orb"
            className="ambient-orb"
            initial={{ scale: 0.84, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.84, opacity: 0 }}
            onClick={() => window.electron?.send?.('toggle-command-bar')}
            title="Open command bar"
          >
            <span>R</span>
            <i />
          </motion.button>
        )}

        {orbState === 'live' && (
          <motion.button
            key="live"
            className="live-strip"
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.94 }}
            onClick={() => window.electron?.send?.('toggle-command-bar')}
          >
            <div className="live-head">
              <span className="rec-dot" />
              <strong>LISTENING</strong>
              <Mic size={13} />
            </div>
            <div className="caption-lines">
              {liveTranscript.slice(-2).map((line, index) => (
                <p key={`${line}-${index}`}>{line}</p>
              ))}
            </div>
            <div className="contact-ticks">
              {detectedContacts.slice(0, 2).map((contact) => (
                <span key={contact}>{contact}</span>
              ))}
            </div>
          </motion.button>
        )}

        {orbState === 'brief' && activeBrief && (
          <PreCallBrief key="brief" brief={activeBrief} onDismiss={() => setActiveBrief(null)} />
        )}
      </AnimatePresence>
    </div>
  )
}
