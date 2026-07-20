import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

// ── Visual constants ───────────────────────────────────────────────────────

const NODE_CONFIG = {
  paper:   { color: '#6366f1', r: 32, icon: '📄' },
  concept: { color: '#8b5cf6', r: 24, icon: '💡' },
  theme:   { color: '#06b6d4', r: 24, icon: '🔬' },
  default: { color: '#64748b', r: 20, icon: '⬡'  },
}

const EDGE_CONFIG = {
  builds_on:    { color: '#10b981', dash: 'none',  label: 'builds on'    },
  contradicts:  { color: '#ef4444', dash: '6,4',   label: 'contradicts'  },
  shares_method:{ color: '#f59e0b', dash: '3,3',   label: 'shares method'},
  shares_theme: { color: '#6366f1', dash: 'none',  label: 'shares theme' },
}

// ── Component ──────────────────────────────────────────────────────────────

export function ConceptMap({ data }) {
  const svgRef = useRef(null)
  const wrapRef = useRef(null)
  const simRef  = useRef(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [hovered, setHovered] = useState(null)

  useEffect(() => {
    if (!data || !data.nodes || data.nodes.length === 0) return
    const el = wrapRef.current
    if (!el) return

    const W = el.clientWidth || 860
    const H = 520

    // Clone data (d3 mutates nodes with x/y/vx/vy)
    const nodes = data.nodes.map(d => ({ ...d }))
    const edges = data.edges.map(d => ({ ...d }))

    // ── SVG setup ──────────────────────────────────────────────────────────
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    svg.attr('width', W).attr('height', H)

    // Gradient background
    const defs = svg.append('defs')
    const bgGrad = defs.append('radialGradient').attr('id', 'bg-grad')
    bgGrad.append('stop').attr('offset', '0%').attr('stop-color', '#0f172a')
    bgGrad.append('stop').attr('offset', '100%').attr('stop-color', '#030712')
    svg.append('rect').attr('width', W).attr('height', H).attr('fill', 'url(#bg-grad)').attr('rx', 16)

    // Arrow markers per relationship type
    Object.entries(EDGE_CONFIG).forEach(([rel, cfg]) => {
      defs.append('marker')
        .attr('id', `arrow-${rel}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', cfg.color)
        .attr('fill-opacity', 0.8)
    })

    // Glow filter
    const glow = defs.append('filter').attr('id', 'glow')
    glow.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'blur')
    const merge = glow.append('feMerge')
    merge.append('feMergeNode').attr('in', 'blur')
    merge.append('feMergeNode').attr('in', 'SourceGraphic')

    // Root group for zoom/pan
    const g = svg.append('g')

    // Zoom
    const zoom = d3.zoom()
      .scaleExtent([0.25, 4])
      .on('zoom', ev => g.attr('transform', ev.transform))
    svg.call(zoom)
    svg.on('dblclick.zoom', null)

    // ── Force simulation ───────────────────────────────────────────────────
    const sim = d3.forceSimulation(nodes)
      .force('link',      d3.forceLink(edges).id(d => d.id).distance(200).strength(0.4))
      .force('charge',    d3.forceManyBody().strength(-700))
      .force('center',    d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius(d => (NODE_CONFIG[d.type]?.r ?? 20) + 20))
      .alphaDecay(0.025)

    simRef.current = sim

    // ── Edges ─────────────────────────────────────────────────────────────
    const linkGroup = g.append('g').attr('class', 'links')
    const link = linkGroup.selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', d => EDGE_CONFIG[d.relationship]?.color ?? '#64748b')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-dasharray', d => EDGE_CONFIG[d.relationship]?.dash ?? 'none')
      .attr('marker-end', d => `url(#arrow-${d.relationship})`)

    // Edge labels
    const linkLabel = g.append('g').attr('class', 'link-labels')
      .selectAll('text')
      .data(edges)
      .join('text')
      .attr('text-anchor', 'middle')
      .attr('fill', d => EDGE_CONFIG[d.relationship]?.color ?? '#64748b')
      .attr('fill-opacity', 0.75)
      .attr('font-size', '10px')
      .attr('font-family', 'Inter, sans-serif')
      .attr('pointer-events', 'none')
      .text(d => EDGE_CONFIG[d.relationship]?.label ?? d.relationship)

    // ── Nodes ─────────────────────────────────────────────────────────────
    const nodeGroup = g.append('g').attr('class', 'nodes')
    const node = nodeGroup.selectAll('g')
      .data(nodes)
      .join('g')
      .attr('cursor', 'grab')
      .call(
        d3.drag()
          .on('start', (ev, d) => {
            if (!ev.active) sim.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y })
          .on('end', (ev, d) => {
            if (!ev.active) sim.alphaTarget(0)
            d.fx = null; d.fy = null
          })
      )
      .on('click', (ev, d) => {
        ev.stopPropagation()
        setSelectedNode(d)
      })
      .on('mouseenter', (ev, d) => setHovered(d.id))
      .on('mouseleave', () => setHovered(null))

    // Outer glow ring (paper nodes)
    node.filter(d => d.type === 'paper')
      .append('circle')
      .attr('r', d => (NODE_CONFIG[d.type]?.r ?? 20) + 8)
      .attr('fill', 'none')
      .attr('stroke', d => NODE_CONFIG[d.type]?.color ?? '#64748b')
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.3)
      .attr('class', 'glow-ring')

    // Main circle
    node.append('circle')
      .attr('r', d => NODE_CONFIG[d.type]?.r ?? 20)
      .attr('fill', d => NODE_CONFIG[d.type]?.color ?? '#64748b')
      .attr('fill-opacity', 0.85)
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.4)
      .attr('filter', d => d.type === 'paper' ? 'url(#glow)' : null)

    // Icon text
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', d => d.type === 'paper' ? '16px' : '13px')
      .attr('pointer-events', 'none')
      .text(d => NODE_CONFIG[d.type]?.icon ?? '⬡')

    // Label below node
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => (NODE_CONFIG[d.type]?.r ?? 20) + 16)
      .attr('fill', '#e2e8f0')
      .attr('font-size', '11px')
      .attr('font-weight', '600')
      .attr('font-family', 'Inter, sans-serif')
      .attr('pointer-events', 'none')
      .text(d => d.label.length > 22 ? d.label.slice(0, 20) + '…' : d.label)

    // ── Tick ──────────────────────────────────────────────────────────────
    sim.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      linkLabel
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // Deselect on canvas click
    svg.on('click', () => setSelectedNode(null))

    return () => { sim.stop() }
  }, [data])

  const nodeConfig = selectedNode ? (NODE_CONFIG[selectedNode.type] ?? NODE_CONFIG.default) : null

  return (
    <div className="concept-map-section">
      <div className="concept-map-canvas" ref={wrapRef}>
        <svg ref={svgRef} style={{ borderRadius: 16, width: '100%' }} />

        {/* Legend */}
        <div className="map-legend">
          <div className="legend-group">
            <span className="legend-heading">Nodes</span>
            {Object.entries(NODE_CONFIG).filter(([k]) => k !== 'default').map(([type, cfg]) => (
              <div key={type} className="legend-item">
                <span className="legend-dot" style={{ background: cfg.color }} />
                <span>{type}</span>
              </div>
            ))}
          </div>
          <div className="legend-divider" />
          <div className="legend-group">
            <span className="legend-heading">Edges</span>
            {Object.entries(EDGE_CONFIG).map(([rel, cfg]) => (
              <div key={rel} className="legend-item">
                <span className="legend-line" style={{
                  background: cfg.color,
                  backgroundImage: cfg.dash !== 'none'
                    ? `repeating-linear-gradient(90deg, ${cfg.color} 0 4px, transparent 4px 8px)`
                    : 'none'
                }} />
                <span>{cfg.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Hint */}
        <div className="map-hint">
          🖱️ Drag nodes · Scroll to zoom · Click for details
        </div>
      </div>

      {/* Selected node panel */}
      {selectedNode && nodeConfig && (
        <div className="node-panel glass-card" style={{ borderColor: nodeConfig.color + '66' }}>
          <button className="node-panel-close" onClick={() => setSelectedNode(null)}>✕</button>
          <div className="node-panel-type" style={{ background: nodeConfig.color }}>
            {nodeConfig.icon} {selectedNode.type}
          </div>
          <h3 className="node-panel-title">{selectedNode.label}</h3>
          <p className="node-panel-desc">
            {selectedNode.description || 'No additional description available.'}
          </p>
          {data.edges
            .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
            .slice(0, 5)
            .map((e, i) => {
              const cfg = EDGE_CONFIG[e.relationship]
              const other = e.source === selectedNode.id ? e.target : e.source
              return (
                <div key={i} className="node-relation" style={{ borderColor: cfg?.color }}>
                  <span style={{ color: cfg?.color }}>{cfg?.label ?? e.relationship}</span>
                  <span> → {other}</span>
                </div>
              )
            })
          }
        </div>
      )}

      {/* Empty state */}
      {(!data || !data.nodes || data.nodes.length === 0) && (
        <div className="map-empty">
          <span>🕸️</span>
          <p>No concept map data available. Try re-analysing the papers.</p>
        </div>
      )}
    </div>
  )
}
