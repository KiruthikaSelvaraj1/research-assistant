export function FutureDirections({ text }) {
  if (!text) return null

  // Parse the labeled output while preserving multi-sentence field descriptions.
  const directions = []
  const blocks = text.split(/(?=^\s*(?:#{1,3}\s*)?\d+[.)]\s+.+$)/m)

  for (const block of blocks) {
    const trimmed = block.trim()
    if (!trimmed) continue

    const titleMatch = trimmed.match(/^(?:#{1,3}\s*)?\d+[.)]\s+(?:\*\*|__)?(.+?)(?:\*\*|__)?\s*(?:\n|$)/)
    if (!titleMatch) continue

    const fieldValue = (label) => {
      const labels = [
        'Research Question',
        'Evidence Gap',
        'Proposed Study',
        'Evaluation\\s*&\\s*Expected Contribution',
      ]
      const nextLabel = labels
        .filter(candidate => candidate !== label)
        .join('|')
      const match = trimmed.match(new RegExp(
        `(?:^|\\n)\\s*(?:[-*]\\s*)?\\*{0,2}${label}\\*{0,2}\\s*:\\s*([\\s\\S]*?)(?=\\n\\s*(?:[-*]\\s*)?\\*{0,2}(?:${nextLabel})\\*{0,2}\\s*:|$)`,
        'i'
      ))
      return match ? match[1].trim() : ''
    }

    directions.push({
      title: titleMatch[1].trim(),
      question: fieldValue('Research Question'),
      gap: fieldValue('Evidence Gap'),
      study: fieldValue('Proposed Study'),
      evaluation: fieldValue('Evaluation\\s*&\\s*Expected Contribution'),
    })
  }

  // If the model did not follow the labeled format, preserve its full response.
  if (directions.length === 0) {
    return (
      <div className="future-section">
        <div className="section-header">
          <h2 className="gradient-text">Future Research Directions</h2>
        </div>
        <div className="glass-card future-raw">
          <pre className="future-text">{text}</pre>
        </div>
      </div>
    )
  }

  return (
    <div className="future-section">
      <div className="section-header">
        <h2 className="gradient-text">Future Research Directions</h2>
        <p className="section-desc">
          Concrete, evidence-grounded research opportunities identified by the
          Research Futurist Agent, each tied to specific findings and limitations.
        </p>
      </div>

      <div className="directions-list">
        {directions.map((d, i) => (
          <div key={i} className="direction-card glass-card">
            <div className="direction-number">{i + 1}</div>
            <div className="direction-body">
              <h3 className="direction-title">{d.title}</h3>

              {d.question && (
                <div className="direction-field">
                  <span className="direction-field-label">🎯 Research Question</span>
                  <p>{d.question}</p>
                </div>
              )}
              {d.gap && (
                <div className="direction-field">
                  <span className="direction-field-label">💡 Evidence Gap</span>
                  <p className="motivation-text"
                    dangerouslySetInnerHTML={{
                      __html: d.gap.replace(
                        /\b(Paper\s+\d+|F\d+_\d+)\b/g,
                        '<mark class="paper-ref">$1</mark>'
                      )
                    }}
                  />
                </div>
              )}
              {d.study && (
                <div className="direction-field">
                  <span className="direction-field-label">🔬 Proposed Study</span>
                  <p>{d.study}</p>
                </div>
              )}
              {d.evaluation && (
                <div className="direction-field">
                  <span className="direction-field-label">📈 Evaluation & Expected Contribution</span>
                  <p>{d.evaluation}</p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
