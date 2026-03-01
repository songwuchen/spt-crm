import { useRef, useEffect, useState, useCallback } from 'react'
import type { Contact } from '@/api/types'

interface Relation {
  id: string
  from_customer_id: string
  to_customer_id: string
  relation_type: string
  to_customer_name?: string
  note?: string
}

interface Customer {
  id: string
  name: string
}

interface Props {
  customerId: string
  customerName: string
  contacts: Contact[]
  relations: Relation[]
  allCustomers: Customer[]
}

interface GraphNode {
  id: string
  label: string
  type: 'center' | 'company' | 'contact'
  subType?: string  // relation_type or role_type
  x: number
  y: number
  vx: number
  vy: number
}

interface GraphEdge {
  source: string
  target: string
  label: string
}

const NODE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  center: { bg: '#3b82f6', border: '#2563eb', text: '#ffffff' },
  parent: { bg: '#6366f1', border: '#4f46e5', text: '#ffffff' },
  subsidiary: { bg: '#8b5cf6', border: '#7c3aed', text: '#ffffff' },
  affiliate: { bg: '#10b981', border: '#059669', text: '#ffffff' },
  partner: { bg: '#f59e0b', border: '#d97706', text: '#ffffff' },
  competitor: { bg: '#ef4444', border: '#dc2626', text: '#ffffff' },
  decision_maker: { bg: '#059669', border: '#047857', text: '#ffffff' },
  influencer: { bg: '#2563eb', border: '#1d4ed8', text: '#ffffff' },
  user: { bg: '#64748b', border: '#475569', text: '#ffffff' },
  finance: { bg: '#d97706', border: '#b45309', text: '#ffffff' },
  procurement: { bg: '#7c3aed', border: '#6d28d9', text: '#ffffff' },
  contact: { bg: '#94a3b8', border: '#64748b', text: '#ffffff' },
}

const RELATION_LABELS: Record<string, string> = {
  parent: '母公司', subsidiary: '子公司', affiliate: '关联企业',
  partner: '合作伙伴', competitor: '竞争对手',
}

const ROLE_LABELS: Record<string, string> = {
  decision_maker: '决策者', influencer: '影响者', user: '使用者',
  finance: '财务', procurement: '采购',
}

export default function CustomerRelationGraph({ customerId, customerName, contacts, relations, allCustomers }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [dragging, setDragging] = useState<string | null>(null)
  const [showContacts, setShowContacts] = useState(true)
  const nodesRef = useRef<GraphNode[]>([])
  const animRef = useRef<number>(0)

  const WIDTH = 900
  const HEIGHT = 520

  // Build graph data
  useEffect(() => {
    const newNodes: GraphNode[] = []
    const newEdges: GraphEdge[] = []

    // Center node
    newNodes.push({
      id: customerId,
      label: customerName,
      type: 'center',
      x: WIDTH / 2,
      y: HEIGHT / 2,
      vx: 0, vy: 0,
    })

    // Relation nodes (companies)
    relations.forEach((r, i) => {
      const relatedId = r.from_customer_id === customerId ? r.to_customer_id : r.from_customer_id
      const relatedName = allCustomers.find((c) => c.id === relatedId)?.name || r.to_customer_name || relatedId.slice(0, 8)
      if (!newNodes.find((n) => n.id === relatedId)) {
        const angle = (2 * Math.PI * i) / Math.max(relations.length, 1)
        newNodes.push({
          id: relatedId,
          label: relatedName,
          type: 'company',
          subType: r.relation_type,
          x: WIDTH / 2 + Math.cos(angle) * 180 + (Math.random() - 0.5) * 40,
          y: HEIGHT / 2 + Math.sin(angle) * 180 + (Math.random() - 0.5) * 40,
          vx: 0, vy: 0,
        })
      }
      newEdges.push({
        source: customerId,
        target: relatedId,
        label: RELATION_LABELS[r.relation_type] || r.relation_type,
      })
    })

    // Contact nodes (decision chain)
    if (showContacts) {
      contacts.forEach((c, i) => {
        const contactId = `contact_${c.id}`
        const angle = (2 * Math.PI * i) / Math.max(contacts.length, 1) + Math.PI / 6
        newNodes.push({
          id: contactId,
          label: c.name,
          type: 'contact',
          subType: c.role_type || 'contact',
          x: WIDTH / 2 + Math.cos(angle) * 120 + (Math.random() - 0.5) * 30,
          y: HEIGHT / 2 + Math.sin(angle) * 120 + (Math.random() - 0.5) * 30,
          vx: 0, vy: 0,
        })
        newEdges.push({
          source: customerId,
          target: contactId,
          label: ROLE_LABELS[c.role_type || ''] || (c.title || '联系人'),
        })
      })
    }

    nodesRef.current = newNodes
    setNodes([...newNodes])
    setEdges(newEdges)
  }, [customerId, customerName, contacts, relations, allCustomers, showContacts])

  // Simple force simulation
  useEffect(() => {
    if (nodes.length <= 1) return

    let tick = 0
    const maxTicks = 120

    const simulate = () => {
      const ns = nodesRef.current
      if (tick >= maxTicks) return

      // Forces
      for (let i = 0; i < ns.length; i++) {
        const n = ns[i]
        // Center gravity
        n.vx += (WIDTH / 2 - n.x) * 0.002
        n.vy += (HEIGHT / 2 - n.y) * 0.002

        // Repulsion
        for (let j = i + 1; j < ns.length; j++) {
          const m = ns[j]
          const dx = n.x - m.x
          const dy = n.y - m.y
          const d = Math.sqrt(dx * dx + dy * dy) || 1
          const force = 3000 / (d * d)
          n.vx += (dx / d) * force
          n.vy += (dy / d) * force
          m.vx -= (dx / d) * force
          m.vy -= (dy / d) * force
        }
      }

      // Edge attraction
      edges.forEach((e) => {
        const s = ns.find((n) => n.id === e.source)
        const t = ns.find((n) => n.id === e.target)
        if (!s || !t) return
        const dx = t.x - s.x
        const dy = t.y - s.y
        const d = Math.sqrt(dx * dx + dy * dy) || 1
        const ideal = t.type === 'contact' ? 120 : 200
        const force = (d - ideal) * 0.005
        if (s.type !== 'center') {
          s.vx += (dx / d) * force
          s.vy += (dy / d) * force
        }
        t.vx -= (dx / d) * force
        t.vy -= (dy / d) * force
      })

      // Apply velocity with damping
      for (const n of ns) {
        if (n.type === 'center') { n.vx = 0; n.vy = 0; continue }
        n.vx *= 0.85
        n.vy *= 0.85
        n.x += n.vx
        n.y += n.vy
        // Bounds
        n.x = Math.max(60, Math.min(WIDTH - 60, n.x))
        n.y = Math.max(40, Math.min(HEIGHT - 40, n.y))
      }

      tick++
      setNodes([...ns])
      animRef.current = requestAnimationFrame(simulate)
    }

    animRef.current = requestAnimationFrame(simulate)
    return () => cancelAnimationFrame(animRef.current)
  }, [edges.length])

  const handleMouseDown = useCallback((nodeId: string) => {
    setDragging(nodeId)
  }, [])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging || !svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const ns = nodesRef.current
    const node = ns.find((n) => n.id === dragging)
    if (node) {
      node.x = x
      node.y = y
      node.vx = 0
      node.vy = 0
      setNodes([...ns])
    }
  }, [dragging])

  const handleMouseUp = useCallback(() => {
    setDragging(null)
  }, [])

  if (relations.length === 0 && contacts.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400 text-sm">
        暂无关联企业或联系人数据，请先添加关系或联系人
      </div>
    )
  }

  const getNodeColor = (node: GraphNode) => {
    if (node.type === 'center') return NODE_COLORS.center
    return NODE_COLORS[node.subType || ''] || NODE_COLORS.contact
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-4 text-xs">
          <span className="text-slate-400 font-bold uppercase">图例:</span>
          {relations.length > 0 && Object.entries(RELATION_LABELS).map(([k, v]) => {
            if (!relations.some((r) => r.relation_type === k)) return null
            const c = NODE_COLORS[k] || NODE_COLORS.contact
            return (
              <span key={k} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full" style={{ background: c.bg }} />
                <span className="text-slate-600">{v}</span>
              </span>
            )
          })}
          {showContacts && contacts.length > 0 && (
            <>
              <span className="text-slate-300">|</span>
              {Object.entries(ROLE_LABELS).map(([k, v]) => {
                if (!contacts.some((c) => c.role_type === k)) return null
                const c = NODE_COLORS[k] || NODE_COLORS.contact
                return (
                  <span key={k} className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded" style={{ background: c.bg }} />
                    <span className="text-slate-600">{v}</span>
                  </span>
                )
              })}
            </>
          )}
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
          <input type="checkbox" checked={showContacts} onChange={(e) => setShowContacts(e.target.checked)}
            className="rounded border-slate-300" />
          显示联系人决策链
        </label>
      </div>

      <div className="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden">
        <svg
          ref={svgRef}
          width={WIDTH}
          height={HEIGHT}
          className="w-full"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="30" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#cbd5e1" />
            </marker>
          </defs>

          {/* Edges */}
          {edges.map((e, i) => {
            const s = nodes.find((n) => n.id === e.source)
            const t = nodes.find((n) => n.id === e.target)
            if (!s || !t) return null
            const mx = (s.x + t.x) / 2
            const my = (s.y + t.y) / 2
            return (
              <g key={`edge-${i}`}>
                <line
                  x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                  stroke={t.type === 'contact' ? '#e2e8f0' : '#cbd5e1'}
                  strokeWidth={t.type === 'contact' ? 1 : 1.5}
                  strokeDasharray={t.type === 'contact' ? '4,3' : undefined}
                  markerEnd="url(#arrow)"
                />
                <rect
                  x={mx - e.label.length * 5.5} y={my - 9}
                  width={e.label.length * 11} height={18}
                  rx={4} fill="white" stroke="#e2e8f0" strokeWidth={0.5}
                />
                <text x={mx} y={my + 3.5} textAnchor="middle" fontSize={10} fill="#94a3b8" fontWeight={500}>
                  {e.label}
                </text>
              </g>
            )
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const color = getNodeColor(node)
            const isCenter = node.type === 'center'
            const isContact = node.type === 'contact'
            const r = isCenter ? 32 : isContact ? 20 : 26

            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onMouseDown={() => handleMouseDown(node.id)}
                style={{ cursor: dragging === node.id ? 'grabbing' : 'grab' }}
              >
                {isCenter && (
                  <circle r={r + 4} fill="none" stroke={color.border} strokeWidth={2} strokeDasharray="4,2" opacity={0.4} />
                )}
                {isContact ? (
                  <rect x={-r} y={-r} width={r * 2} height={r * 2} rx={6}
                    fill={color.bg} stroke={color.border} strokeWidth={1.5} />
                ) : (
                  <circle r={r} fill={color.bg} stroke={color.border} strokeWidth={2} />
                )}
                <text y={1} textAnchor="middle" fontSize={isCenter ? 13 : 10}
                  fill={color.text} fontWeight={isCenter ? 700 : 600}
                  dominantBaseline="middle">
                  {node.label.length > 6 ? node.label.slice(0, 5) + '..' : node.label}
                </text>
                {/* Full label below for truncated names */}
                {node.label.length > 6 && (
                  <text y={r + 14} textAnchor="middle" fontSize={10} fill="#64748b" fontWeight={500}>
                    {node.label}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
