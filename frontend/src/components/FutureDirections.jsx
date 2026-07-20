export function FutureDirections({ text }) {
  if (!text) return null

  // Parse the formatted output into structured directions
  const directions = []
  const blocks = text.split(/(?=\d+\.\s+\*\*)/)

  for (const block of blocks) {
    const trimmed = block.trim()
    if (!trimmed) continue

    const titleMatch = trimmed.match(/^\d+\.\s+\*\*(.+?)\*\*/)
    const dirMatch   = trimmed.match(/Research Direction:\s*(.+?)(?=\n|Motivation:|$)/s)
    const motMatch   = trimmed.match(/Motivation:\s*(.+?)(?=\n\s*Approach:|$)/s)
    const appMatch   = trimmed.match(/Approach:\s*(.+?)(?=\n\s*\d+\.|$)/s)

    directions.push({
      title:      titleMatch  ? titleMatch[1].trim()  : `Direction ${directions.length + 1}`,
      direction:  dirMatch    ? dirMatch[1].trim()    : trimmed.slice(0, 200),
      motivation: motMatch    ? motMatch[1].trim()    : '',
      approach:   appMatch    ? appMatch[1].trim()    : '',
    })
  }

  // Fallback: if parsing failed, show raw text
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

              {d.direction && (
                <div className="direction-field">
                  <span className="direction-field-label">🎯 Research Direction</span>
                  <p>{d.direction}</p>
                </div>
              )}
              {d.motivation && (
                <div className="direction-field">
                  <span className="direction-field-label">💡 Motivation</span>
                  <p className="motivation-text"
                    dangerouslySetInnerHTML={{
                      __html: d.motivation.replace(
                        /\b(Paper\s+\d+|F\d+_\d+)\b/g,
                        '<mark class="paper-ref">$1</mark>'
                      )
                    }}
                  />
                </div>
              )}
              {d.approach && (
                <div className="direction-field">
                  <span className="direction-field-label">🔬 Approach</span>
                  <p>{d.approach}</p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
