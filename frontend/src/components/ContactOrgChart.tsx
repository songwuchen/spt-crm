import { useMemo } from 'react'
import type { Contact } from '@/api/types'

import Icon from '@/components/Icon'
interface ContactOrgChartProps {
  contacts: Contact[]
  onSelect?: (contact: Contact) => void
}

const roleConfig: Record<string, { label: string; color: string; bg: string }> = {
  decision_maker: { label: '决策者', color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-300' },
  influencer: { label: '影响者', color: 'text-blue-700', bg: 'bg-blue-50 border-blue-300' },
  user: { label: '使用者', color: 'text-slate-700', bg: 'bg-slate-50 border-slate-300' },
  finance: { label: '财务', color: 'text-amber-700', bg: 'bg-amber-50 border-amber-300' },
  procurement: { label: '采购', color: 'text-purple-700', bg: 'bg-purple-50 border-purple-300' },
}

interface TreeNode {
  contact: Contact
  children: TreeNode[]
}

function buildTree(contacts: Contact[]): TreeNode[] {
  const map = new Map<string, TreeNode>()
  const roots: TreeNode[] = []

  for (const c of contacts) {
    map.set(c.id, { contact: c, children: [] })
  }

  for (const c of contacts) {
    const node = map.get(c.id)!
    if (c.reports_to_id && map.has(c.reports_to_id)) {
      map.get(c.reports_to_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  }

  return roots
}

function ContactNode({ node, onSelect }: { node: TreeNode; onSelect?: (c: Contact) => void }) {
  const c = node.contact
  const role = roleConfig[c.role_type || ''] || { label: c.role_type || '', color: 'text-slate-600', bg: 'bg-white border-slate-200' }

  return (
    <div className="flex flex-col items-center">
      {/* Node card */}
      <div
        className={`relative border-2 rounded-xl px-4 py-3 min-w-[140px] cursor-pointer hover:shadow-md transition-shadow ${role.bg}`}
        onClick={() => onSelect?.(c)}
      >
        {c.is_primary && (
          <span className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-amber-400 flex items-center justify-center">
            <Icon name="star" className="text-white" style={{ fontSize: 12 }} />
          </span>
        )}
        <div className="text-sm font-bold text-slate-800 text-center">{c.name}</div>
        {c.title && <div className="text-[13px] text-slate-500 text-center truncate">{c.title}</div>}
        <div className={`text-[12px] font-bold text-center mt-1 ${role.color}`}>{role.label}</div>
      </div>

      {/* Children */}
      {node.children.length > 0 && (
        <>
          {/* Vertical line down */}
          <div className="w-px h-5 bg-slate-300" />
          {/* Horizontal connector + children */}
          <div className="relative flex gap-6">
            {node.children.length > 1 && (
              <div className="absolute top-0 left-[50%] h-px bg-slate-300"
                style={{
                  left: `calc(50% / ${node.children.length})`,
                  width: `calc(100% - 100% / ${node.children.length})`,
                }} />
            )}
            {node.children.map((child) => (
              <div key={child.contact.id} className="flex flex-col items-center">
                <div className="w-px h-5 bg-slate-300" />
                <ContactNode node={child} onSelect={onSelect} />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export default function ContactOrgChart({ contacts, onSelect }: ContactOrgChartProps) {
  const tree = useMemo(() => buildTree(contacts), [contacts])

  if (contacts.length === 0) {
    return <div className="text-center text-slate-400 text-sm py-8">暂无联系人</div>
  }

  return (
    <div className="overflow-auto py-4">
      <div className="flex gap-8 justify-center items-start min-w-max px-4">
        {tree.map((root) => (
          <ContactNode key={root.contact.id} node={root} onSelect={onSelect} />
        ))}
      </div>
      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-6 flex-wrap">
        {Object.entries(roleConfig).map(([, cfg]) => (
          <div key={cfg.label} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded border-2 ${cfg.bg}`} />
            <span className={`text-[12px] font-bold ${cfg.color}`}>{cfg.label}</span>
          </div>
        ))}
        <div className="flex items-center gap-1">
          <span className="w-4 h-4 rounded-full bg-amber-400 flex items-center justify-center">
            <Icon name="star" className="text-white" style={{ fontSize: 10 }} />
          </span>
          <span className="text-[12px] font-bold text-amber-600">主要联系人</span>
        </div>
      </div>
    </div>
  )
}
