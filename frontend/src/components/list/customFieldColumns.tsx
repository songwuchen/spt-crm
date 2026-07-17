// 由实体扩展字段定义生成列表列(自定义字段「调出显示」)。
// 值存于 record.custom_fields_json[fieldId];按字段类型简单格式化。
// 跳过明细子表/文件/图片/签名/富文本等非标量类型——窄列里只会渲染成 [object Object]。
import type { ColumnsType } from 'antd/es/table'

export interface CustomFieldDef {
  id: string
  label: string
  type: string
}

const LIST_SKIP_TYPES = new Set([
  'detail_table', 'sub_table_data', 'file', 'image', 'signature', 'rich_text',
])

/** 生成自定义字段列。每列带 `__customField` 标记,供 useListView 识别为「默认隐藏、可调出」。 */
export function buildCustomFieldColumns<T = any>(defs: CustomFieldDef[]): ColumnsType<T> {
  return (defs || [])
    .filter((f) => f.id && !LIST_SKIP_TYPES.has(f.type))
    .map((f) => ({
      title: f.label,
      key: `cf_${f.id}`,
      width: 140,
      __customField: true,
      render: (_: unknown, r: any) => {
        const raw = (r.custom_fields_json || {})[f.id]
        if (raw == null || raw === '' || (Array.isArray(raw) && raw.length === 0)) {
          return <span className="text-slate-300">-</span>
        }
        if (f.type === 'switch') return raw ? '是' : '否'
        if (Array.isArray(raw)) return raw.join('、')
        return <span className="text-sm text-slate-700">{String(raw)}</span>
      },
    } as any))
}
