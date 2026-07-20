const AGENT_STEPS = [
  { key: 'ingestion',   label: 'Ingestion Agent',         icon: '📥', desc: 'Extracting text and detecting sections from PDFs' },
  { key: 'summarizer',  label: 'Summarizer Agent',         icon: '✍️',  desc: 'Writing 150-250 word summaries for each paper' },
  { key: 'findings',    label: 'Key Findings Agent',       icon: '🔍', desc: 'Extracting structured claims, metrics, and limitations' },
  { key: 'synthesis',   label: 'Synthesis Agent',          icon: '📚', desc: 'Synthesising cross-paper literature review and concept map' },
  { key: 'future',      label: 'Future Directions Agent',  icon: '🚀', desc: 'Identifying research gaps and future opportunities' },
]

function stepStatus(stepIndex, progress, overallStatus) {
  if (overallStatus === 'queued') return 'pending'
  // Map progress events to steps
  const runningSteps = progress.filter(p => p.status === 'running').map(p => p.step)
  const completedSteps = progress.filter(p => p.status === 'complete').map(p => p.step)
  const s = stepIndex + 1
  if (completedSteps.includes(s) || overallStatus === 'complete') return 'complete'
  if (runningSteps.includes(s)) return 'running'
  // If any later step is running, this one is done
  if (runningSteps.some(r => r > s)) return 'complete'
  return 'pending'
}

export function ProgressTracker({ progress, status }) {
  const lastMessage = progress.length > 0
    ? progress[progress.length - 1].message
    : 'Initialising agents…'

  return (
    <div className="progress-wrapper">
      <div className="progress-header">
        <div className="progress-brain">🧠</div>
        <div>
          <h2 className="gradient-text">Agents at Work</h2>
          <p className="progress-status-msg">{lastMessage}</p>
        </div>
      </div>

      <div className="agent-steps">
        {AGENT_STEPS.map((step, i) => {
          const s = stepStatus(i, progress, status)
          return (
            <div key={step.key} className={`agent-step ${s}`}>
              <div className="step-indicator">
                {s === 'complete' ? (
                  <span className="step-check">✓</span>
                ) : s === 'running' ? (
                  <span className="step-pulse" />
                ) : (
                  <span className="step-dot" />
                )}
                {i < AGENT_STEPS.length - 1 && <div className={`step-line ${s === 'complete' ? 'done' : ''}`} />}
              </div>
              <div className="step-content">
                <div className="step-header">
                  <span className="step-icon">{step.icon}</span>
                  <span className="step-label">{step.label}</span>
                  {s === 'running' && <span className="running-badge">running</span>}
                  {s === 'complete' && <span className="done-badge">done</span>}
                </div>
                <p className="step-desc">{step.desc}</p>
              </div>
            </div>
          )
        })}
      </div>

      <div className="progress-bar-wrap">
        <div
          className="progress-bar-fill"
          style={{
            width: `${Math.min(100, (progress.filter(p => p.status === 'complete' || p.status === 'running').length / 6) * 100)}%`
          }}
        />
      </div>
      <p className="progress-hint">This typically takes 1-2 minutes for 2-3 papers.</p>
    </div>
  )
}
