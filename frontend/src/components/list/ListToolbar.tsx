import { useEffect, useState } from 'react'
import { Button, Badge, Select } from 'antd'
import { FilterOutlined, SortAscendingOutlined, SortDescendingOutlined } from '@ant-design/icons'
import AdvancedFilter from '@/components/AdvancedFilter/AdvancedFilter'
import ColumnConfigPanel from './ColumnConfigPanel'
import ViewManager from './ViewManager'
import { getSearchSchema, type SchemaField } from '@/api/searchSchema'
import type { ListViewController } from '@/hooks/useListView'

interface Props {
  resource: string
  view: ListViewController
  /** 当筛选/排序/视图变化、需要重新拉取数据时调用（通常回到第 1 页）。 */
  onChange: () => void
}

/**
 * 列表工具条：高级筛选(多字段/多条件) + 排序 + 列配置 + 保存视图。
 * 自身负责拉取资源字段 schema；页面只需提供 useListView 控制器与刷新回调。
 */
export default function ListToolbar({ resource, view, onChange }: Props) {
  const [fields, setFields] = useState<SchemaField[]>([])
  const [filterOpen, setFilterOpen] = useState(false)

  useEffect(() => {
    let alive = true
    getSearchSchema(resource).then((res) => {
      if (alive) setFields(res.data?.fields || [])
    }).catch(() => { /* schema 拉取失败时禁用高级筛选 */ })
    return () => { alive = false }
  }, [resource])

  const sortableFields = fields.filter((f) => f.sortable !== false)

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Badge count={view.activeCount} size="small">
        <Button icon={<FilterOutlined />} onClick={() => setFilterOpen(true)} disabled={!fields.length}>
          高级筛选
        </Button>
      </Badge>

      {/* 排序 */}
      <Select
        placeholder="排序字段" allowClear size="middle" style={{ width: 130 }}
        value={view.sort?.by}
        onChange={(by) => { view.setSort(by ? { by, order: view.sort?.order || 'desc' } : null); onChange() }}
        options={sortableFields.map((f) => ({ value: f.key, label: f.label }))}
      />
      {view.sort && (
        <Button
          icon={view.sort.order === 'asc' ? <SortAscendingOutlined /> : <SortDescendingOutlined />}
          onClick={() => { view.setSort({ by: view.sort!.by, order: view.sort!.order === 'asc' ? 'desc' : 'asc' }); onChange() }}
          title={view.sort.order === 'asc' ? '升序' : '降序'}
        />
      )}

      <ColumnConfigPanel allMeta={view.allMeta} colState={view.colState} onChange={view.setColState} onReset={view.resetColumns} />

      <ViewManager page={resource} view={view} onApplied={onChange} />

      <AdvancedFilter
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        fields={fields}
        value={view.advanced}
        onApply={(dsl) => { view.setAdvanced(dsl); onChange() }}
      />
    </div>
  )
}
