export function LitReview({ text, papers }) {
  if (!text) return null

  // Highlight Paper 1, Paper 2, ... references in the text
  const highlighted = text.replace(
    /\b(Paper\s+\d+)\b/g,
    '<mark class="paper-ref">$1</mark>'
  )

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
        <div
          className="litreview-text"
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      </div>
    </div>
  )
}
