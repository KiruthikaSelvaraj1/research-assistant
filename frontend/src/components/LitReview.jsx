export function LitReview({ text, papers }) {
  if (!text) return null

  const sections = text
    .split(/(?=^#{1,3}\s+.+$)/m)
    .map(section => section.trim())
    .filter(Boolean)

  const renderReferences = value => value
    .split(/(\bPaper\s+\d+|\bF\d+_\d+\b)/g)
    .map((part, index) => (
      /^(Paper\s+\d+|F\d+_\d+)$/.test(part)
        ? <mark key={index} className="paper-ref">{part}</mark>
        : part
    ))

  return (
    <div className="litreview-section">
      <div className="section-header">
        <h2 className="gradient-text">Synthesised Literature Review</h2>
        <p className="section-desc">
          Cross-paper analysis identifying agreements, contradictions, methodological
          differences, and open questions — synthesised by the Literature Review Agent.
        </p>
      </div>

      {/* Paper quick-ref chips */}
      {papers && papers.length > 0 && (
        <div className="paper-chips">
          {papers.map(p => (
            <span key={p.paper_index} className="paper-chip">
              Paper {p.paper_index}: {p.filename}
            </span>
          ))}
        </div>
      )}

      <div className="glass-card litreview-body">
        <div className="litreview-text">
          {sections.map((section, index) => {
            const [firstLine, ...rest] = section.split('\n')
            const heading = firstLine.match(/^#{1,3}\s+(.+)$/)
            const body = heading ? rest.join('\n').trim() : section

            return (
              <section key={index} className="litreview-subsection">
                {heading && <h3>{heading[1]}</h3>}
                {body.split(/\n\s*\n/).filter(Boolean).map((paragraph, paragraphIndex) => (
                  <p key={paragraphIndex}>{renderReferences(paragraph)}</p>
                ))}
              </section>
            )
          })}
        </div>
      </div>
    </div>
  )
}
