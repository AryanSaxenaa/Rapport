import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, Mic } from 'lucide-react'
import { PreCallBrief } from './PreCallBrief'
import { useRapportStore } from '../store/rapport-store'

type OrbState = 'idle' | 'loading' | 'live' | 'brief'

export function FloatingOrb() {
  const {
    isRecording,
    activeBrief,
    briefLoading,
    liveTranscript,
    detectedContacts,
    setActiveBrief,
    minimized,
    setMinimized,
  } = useRapportStore()
  const [orbState, setOrbState] = useState<OrbState>('idle')

  useEffect(() => {
    if (briefLoading) setOrbState('loading')
    else if (activeBrief) setOrbState('brief')
    else if (isRecording) setOrbState('live')
    else setOrbState('idle')
  }, [isRecording, activeBrief, briefLoading])

  async function toggleMinimized() {
    // BUG-30: Read minimized from the store snapshot at call-time so we
    // always toggle the current value, not a stale closure.  `setMinimized`
    // is already available from the hook above, so we don't need getState().
    const next = !minimized
    setMinimized(next)
    if (next) {
      await window.electron?.minimizeWindow?.()
    } else {
      await window.electron?.restoreWindow?.()
    }
  }

  return (
    <div className="orb-anchor">
      <AnimatePresence mode="wait">
        {orbState === 'idle' && (
          <motion.button
            key="orb"
            className="ambient-orb"
            drag
            dragConstraints={{ left: -300, right: 0, top: -600, bottom: 0 }}
            dragElastic={0.1}
            dragMomentum={false}
            initial={{ scale: 0.5, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.8, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 260, damping: 20 }}
            onClick={toggleMinimized}
            title={minimized ? 'Expand Rapport' : 'Minimize Rapport'}
          >
            <span>R</span>
            <i />
          </motion.button>
        )}

        {orbState === 'loading' && (
          <motion.button
            key="loading"
            className="ambient-orb loading"
            drag
            dragConstraints={{ left: -300, right: 0, top: -600, bottom: 0 }}
            dragElastic={0.1}
            dragMomentum={false}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.8, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          >
            <Loader2 size={20} className="spin" />
            <i className="loading-ring" />
          </motion.button>
        )}

        {orbState === 'live' && (
          <motion.button
            key="live"
            className="live-strip"
            drag
            dragConstraints={{ left: -200, right: 0, top: -600, bottom: 0 }}
            dragElastic={0.1}
            dragMomentum={false}
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 10 }}
            transition={{ type: 'spring', stiffness: 260, damping: 24 }}
            onClick={toggleMinimized}
          >
            <div className="live-head">
              <span className="rec-dot" />
              <strong>LISTENING</strong>
              <Mic size={13} />
            </div>
            <div className="caption-lines">
              {liveTranscript.length > 0 ? (
                liveTranscript.slice(-2).map((line, index) => (
                  <motion.p
                    key={`${line}-${index}`}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 }}
                  >
                    {line}
                  </motion.p>
                ))
              ) : (
                <p className="dim-text">Waiting for audio input…</p>
              )}
            </div>
            <div className="contact-ticks">
              {detectedContacts.slice(0, 3).map((contact) => (
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
