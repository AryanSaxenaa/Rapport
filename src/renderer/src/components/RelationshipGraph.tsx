import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

type Node = { id: string; name: string; company: string; stance: string; type: 'person' | 'company' | 'topic' }
type Link = { source: string; target: string; type: string; strength: number }

export function RelationshipGraph({ nodes, links }: { nodes: Node[]; links: Link[] }) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current) return

    const width = 390
    const height = 250
    const localNodes = nodes.map((node) => ({ ...node }))
    const localLinks = links.map((link) => ({ ...link }))

    const svg = d3.select(svgRef.current).attr('viewBox', `0 0 ${width} ${height}`)
    svg.selectAll('*').remove()

    const defs = svg.append('defs')
    const pattern = defs
      .append('pattern')
      .attr('id', 'graph-dots')
      .attr('width', 18)
      .attr('height', 18)
      .attr('patternUnits', 'userSpaceOnUse')

    pattern.append('circle').attr('cx', 9).attr('cy', 9).attr('r', 0.9).attr('fill', '#262626')
    svg.append('rect').attr('width', width).attr('height', height).attr('fill', 'url(#graph-dots)')

    const stanceColor = (stance: string) =>
      ({ champion: '#54c878', skeptic: '#df5f3b', neutral: '#7a7a7a', blocker: '#d75b5b' })[stance] ?? '#5f5f5f'

    const simulation = d3
      .forceSimulation(localNodes as d3.SimulationNodeDatum[])
      .force('link', d3.forceLink(localLinks).id((node: any) => node.id).distance(76))
      .force('charge', d3.forceManyBody().strength(-145))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius(30))

    const link = svg
      .append('g')
      .selectAll('line')
      .data(localLinks)
      .join('line')
      .attr('stroke', '#3a3a3a')
      .attr('stroke-width', (item) => item.strength * 1.8)

    const label = svg
      .append('g')
      .selectAll('text')
      .data(localLinks)
      .join('text')
      .attr('font-family', 'Silkscreen, monospace')
      .attr('font-size', '7')
      .attr('fill', '#666')
      .attr('text-anchor', 'middle')
      .text((item) => item.type.toUpperCase())

    const dragBehavior = d3
      .drag<SVGGElement, any>()
      .on('start', (event, item) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        item.fx = item.x
        item.fy = item.y
      })
      .on('drag', (event, item) => {
        item.fx = event.x
        item.fy = event.y
      })
      .on('end', (event, item) => {
        if (!event.active) simulation.alphaTarget(0)
        item.fx = null
        item.fy = null
      })

    const node = svg
      .append('g')
      .selectAll<SVGGElement, any>('g')
      .data(localNodes)
      .join('g')
      .call(dragBehavior)

    node
      .append('circle')
      .attr('r', (item) => (item.type === 'company' ? 15 : item.type === 'topic' ? 12 : 10))
      .attr('fill', '#101010')
      .attr('stroke', (item) => (item.type === 'person' ? stanceColor(item.stance) : '#696969'))
      .attr('stroke-width', 1.4)

    node
      .append('text')
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('font-family', 'Silkscreen, monospace')
      .attr('font-size', '8')
      .attr('fill', '#f2f2f2')
      .text((item) => item.name.slice(0, 5).toUpperCase())

    simulation.on('tick', () => {
      link
        .attr('x1', (item: any) => item.source.x)
        .attr('y1', (item: any) => item.source.y)
        .attr('x2', (item: any) => item.target.x)
        .attr('y2', (item: any) => item.target.y)

      label
        .attr('x', (item: any) => (item.source.x + item.target.x) / 2)
        .attr('y', (item: any) => (item.source.y + item.target.y) / 2)

      node.attr('transform', (item: any) => `translate(${item.x},${item.y})`)
    })

    return () => {
      simulation.stop()
    }
  }, [nodes, links])

  return (
    <section className="graph-panel">
      <div className="panel-heading">
        <span>RELATIONSHIP GRAPH</span>
      </div>
      <svg ref={svgRef} />
    </section>
  )
}
