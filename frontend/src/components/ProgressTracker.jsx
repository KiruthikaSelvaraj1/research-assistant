const AGENT_STEPS = [
  { key: 'extraction', label: 'PDF Extraction', icon: '📥', desc: 'Extracting text and detecting sections locally' },
  { key: 'paper-analysis', label: 'Paper Analysis', icon: '🔍', desc: 'Writing a summary and structured findings for each paper' },
  { key: 'synthesis', label: 'Comparative Synthesis', icon: '📚', desc: 'Comparing evidence and mapping concepts across papers' },
  { key: 'future', label: 'Future Directions', icon: '🚀', desc: 'Developing evidence-grounded research proposals' },
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
            width: `${Math.min(100, (progress.filter(p => p.status === 'complete').length / AGENT_STEPS.length) * 100)}%`
          }}
        />
      </div>
      <p className="progress-hint">
        Timing depends on paper length, hardware, and model. Local models may take several minutes.
      </p>
    </div>
  )
}
