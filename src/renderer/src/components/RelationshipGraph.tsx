import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { GraphNode, GraphEdge, EvidenceItem } from '../store/rapport-store'

const EDGE_COLORS = {
  red: '#df5f3b',
  amber: '#c9921a',
  green: '#54c878',
  grey: '#5a5a5a',
}

type SimNode = GraphNode & d3.SimulationNodeDatum

type EvidencePanel = {
  edge: GraphEdge
  x: number
  y: number
}

export function RelationshipGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [evidence, setEvidence] = useState<EvidencePanel | null>(null)

  useEffect(() => {
    if (!svgRef.current) return
    setEvidence(null)

    const width = 390
    const height = 260
    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }))

    type SimLink = Omit<GraphEdge, 'from' | 'to'> & d3.SimulationLinkDatum<SimNode> & {
      source: string | SimNode
      target: string | SimNode
      originalEdge: GraphEdge
    }
    const simLinks: SimLink[] = edges.map((e) => ({
      ...e,
      source: e.from,
      target: e.to,
      originalEdge: e,
    }))

    const svg = d3.select(svgRef.current).attr('viewBox', `0 0 ${width} ${height}`)
    svg.selectAll('*').remove()

    const defs = svg.append('defs')

    Object.entries(EDGE_COLORS).forEach(([key, color]) => {
      defs.append('marker')
        .attr('id', `arrow-${key}`)
        .attr('viewBox', '0 -4 8 8')
        .attr('refX', 18)
        .attr('refY', 0)
        .attr('markerWidth', 5)
        .attr('markerHeight', 5)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', color)
    })

    const dotPattern = defs.append('pattern')
      .attr('id', 'graph-dots')
      .attr('width', 18)
      .attr('height', 18)
      .attr('patternUnits', 'userSpaceOnUse')
    dotPattern.append('circle').attr('cx', 9).attr('cy', 9).attr('r', 0.9).attr('fill', '#262626')
    svg.append('rect').attr('width', width).attr('height', height).attr('fill', 'url(#graph-dots)')

    const simulation = d3
      .forceSimulation<SimNode>(simNodes)
      .force('link', d3.forceLink<SimNode, SimLink>(simLinks).id((d) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-160))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide<SimNode>().radius((d) => nodeRadius(d) + 6))

    const linkG = svg.append('g')
    const link = linkG
      .selectAll<SVGLineElement, SimLink>('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', (d) => EDGE_COLORS[d.color] ?? EDGE_COLORS.grey)
      .attr('stroke-width', (d) => Math.max(1, Math.min(4, d.weight * 1.5)))
      .attr('stroke-opacity', 0.85)
      .attr('marker-end', (d) => `url(#arrow-${d.color})`)
      .style('cursor', 'pointer')
      .on('click', (event: MouseEvent, d) => {
        event.stopPropagation()
        // BUG-27: event.offsetX/Y is relative to the clicked child element
        // (the <line>), not the SVG container — so the panel appeared at a
        // seemingly random position.  Use clientX/Y minus the SVG bounding
        // rect to get coordinates relative to the container div.
        const svgRect = svgRef.current?.getBoundingClientRect()
        const x = svgRect ? event.clientX - svgRect.left : event.offsetX
        const y = svgRect ? event.clientY - svgRect.top  : event.offsetY
        setEvidence({ edge: d.originalEdge, x, y })
      })

    const nodeG = svg.append('g')
    const drag = d3.drag<SVGGElement, SimNode>()
      .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null })

    const node = nodeG
      .selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .join('g')
      .call(drag)
      .style('cursor', 'pointer')

    node.append('circle')
      .attr('r', nodeRadius)
      .attr('fill', '#101010')
      .attr('stroke', '#4a9eff')
      .attr('stroke-width', (d) => 1 + d.importance * 1.5)

    node.append('text')
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('font-family', 'Silkscreen, monospace')
      .attr('font-size', '7')
      .attr('fill', '#f2f2f2')
      .attr('pointer-events', 'none')
      .text((d) => d.label.split(' ')[0].slice(0, 6).toUpperCase())

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x ?? 0)
        .attr('y1', (d) => (d.source as SimNode).y ?? 0)
        .attr('x2', (d) => (d.target as SimNode).x ?? 0)
        .attr('y2', (d) => (d.target as SimNode).y ?? 0)
      node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    svg.on('click', () => setEvidence(null))

    return () => { simulation.stop() }
  }, [nodes, edges])

  return (
    <section className="graph-panel">
      <div className="panel-heading">
        <span>RELATIONSHIP GRAPH</span>
        {edges.length > 0 && (
          <span style={{ fontSize: 9, color: 'var(--n-dim)', marginLeft: 8 }}>
            {edges.length} edge{edges.length !== 1 ? 's' : ''} · click edge for evidence
          </span>
        )}
      </div>
      {edges.length === 0 ? (
        <div className="graph-empty-state">
          Not enough evidence yet — ingest emails or record a call.
        </div>
      ) : (
        <div style={{ position: 'relative' }}>
          <svg ref={svgRef} />
          {evidence && (
            <div className="evidence-panel" style={{ top: evidence.y, left: Math.min(evidence.x, 220) }}>
              <div className="evidence-panel-header">
                <span style={{ color: EDGE_COLORS[evidence.edge.color] }}>
                  {evidence.edge.type.toUpperCase()}
                </span>
                <span style={{ color: 'var(--n-dim)', fontSize: 9 }}>
                  {evidence.edge.from} → {evidence.edge.to}
                </span>
              </div>
              {evidence.edge.evidence.length === 0 ? (
                <p style={{ color: 'var(--n-dim)', fontSize: 10 }}>No source quotes stored.</p>
              ) : (
                evidence.edge.evidence.map((item: EvidenceItem, i: number) => (
                  <div key={i} className="evidence-quote">
                    <span style={{ color: 'var(--n-dim)', fontSize: 9 }}>{item.date}</span>
                    <p>"{item.quote}"</p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function nodeRadius(d: SimNode): number {
  return 7 + d.importance * 10
}
