import { Dropdown, Button, Checkbox, Tag } from 'antd'
import { SettingOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons'
import type { ColumnState, ColMeta } from '@/hooks/useListView'

interface Props {
  allMeta: ColMeta[]
  colState: ColumnState
  onChange: (cs: ColumnState) => void
  onReset: () => void
}

/** 列配置：显隐 + 上下移排序 + 恢复默认。自定义字段列默认隐藏，勾选即「调出显示」。 */
export default function ColumnConfigPanel({ allMeta, colState, onChange, onReset }: Props) {
  // 有效顺序 = 已保存顺序(过滤掉已不存在的) + 其余按原始顺序补齐
  const known = allMeta.map((m) => m.key)
  const ordered = [
    ...colState.order.filter((k) => known.includes(k)),
    ...known.filter((k) => !colState.order.includes(k)),
  ]
  const metaByKey = new Map(allMeta.map((m) => [m.key, m]))
  const shown = colState.shown || []

  const isChecked = (m: ColMeta) =>
    m.optIn ? shown.includes(m.key) : !colState.hidden.includes(m.key)

  const move = (idx: number, dir: -1 | 1) => {
    const next = [...ordered]
    const j = idx + dir
    if (j < 0 || j >= next.length) return
    ;[next[idx], next[j]] = [next[j], next[idx]]
    onChange({ ...colState, order: next })
  }

  const toggle = (m: ColMeta, visible: boolean) => {
    if (m.optIn) {
      // 自定义字段列：用 shown 白名单控制
      const nextShown = visible ? [...shown, m.key] : shown.filter((k) => k !== m.key)
      onChange({ ...colState, shown: nextShown })
    } else {
      const hidden = visible
        ? colState.hidden.filter((k) => k !== m.key)
        : [...colState.hidden, m.key]
      onChange({ ...colState, hidden })
    }
  }

  return (
    <Dropdown trigger={['click']} dropdownRender={() => (
      <div className="bg-white rounded-lg border border-slate-200 shadow-lg p-2 min-w-[240px] max-h-[360px] overflow-auto">
        <div className="flex items-center justify-between px-1 pb-2 mb-1 border-b border-slate-100">
          <span className="text-xs font-bold text-slate-400 uppercase">列配置</span>
          <a className="text-xs text-primary" onClick={onReset}>恢复默认</a>
        </div>
        {ordered.map((key, idx) => {
          const m = metaByKey.get(key)
          if (!m) return null
          return (
            <div key={key} className="flex items-center gap-2 py-0.5 px-1 hover:bg-slate-50 rounded">
              <Checkbox
                checked={isChecked(m)}
                onChange={(e) => toggle(m, e.target.checked)}
              />
              <span className="flex-1 text-sm text-slate-700 truncate">{m.title}</span>
              {m.custom && <Tag color="blue" style={{ marginInlineEnd: 0, transform: 'scale(0.85)' }}>自定义</Tag>}
              <Button type="text" size="small" icon={<ArrowUpOutlined />} disabled={idx === 0} onClick={() => move(idx, -1)} />
              <Button type="text" size="small" icon={<ArrowDownOutlined />} disabled={idx === ordered.length - 1} onClick={() => move(idx, 1)} />
            </div>
          )
        })}
      </div>
    )}>
      <Button icon={<SettingOutlined />}>列配置</Button>
    </Dropdown>
  )
}
