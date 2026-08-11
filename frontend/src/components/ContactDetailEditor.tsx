/** 客户表单「联系人明细」子表：对齐简道云 联系人/所在部门/职位/电话 */
import { Button, Input, Table } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

export type ContactDraftRow = {
  _key: string
  id?: string
  name?: string
  department?: string
  title?: string
  phone?: string
}

let keySeq = 0
export function emptyContactRow(): ContactDraftRow {
  keySeq += 1
  return { _key: `c_${Date.now()}_${keySeq}`, name: '', department: '', title: '', phone: '' }
}

export default function ContactDetailEditor({
  value,
  onChange,
}: {
  value: ContactDraftRow[]
  onChange: (rows: ContactDraftRow[]) => void
}) {
  const rows = value?.length ? value : [emptyContactRow()]

  const setCell = (key: string, field: keyof ContactDraftRow, v: string) => {
    onChange(rows.map((r) => (r._key === key ? { ...r, [field]: v } : r)))
  }

  const columns: ColumnsType<ContactDraftRow> = [
    {
      title: '联系人',
      dataIndex: 'name',
      render: (_, r) => (
        <Input
          value={r.name}
          placeholder="姓名"
          onChange={(e) => setCell(r._key, 'name', e.target.value)}
        />
      ),
    },
    {
      title: '所在部门',
      dataIndex: 'department',
      render: (_, r) => (
        <Input
          value={r.department}
          placeholder="部门"
          onChange={(e) => setCell(r._key, 'department', e.target.value)}
        />
      ),
    },
    {
      title: '职位',
      dataIndex: 'title',
      render: (_, r) => (
        <Input
          value={r.title}
          placeholder="职位"
          onChange={(e) => setCell(r._key, 'title', e.target.value)}
        />
      ),
    },
    {
      title: '电话',
      dataIndex: 'phone',
      render: (_, r) => (
        <Input
          value={r.phone}
          placeholder="电话"
          onChange={(e) => setCell(r._key, 'phone', e.target.value)}
        />
      ),
    },
    {
      title: '',
      width: 48,
      render: (_, r) => (
        <Button
          type="text"
          danger
          size="small"
          icon={<DeleteOutlined />}
          disabled={rows.length <= 1}
          onClick={() => onChange(rows.filter((x) => x._key !== r._key))}
        />
      ),
    },
  ]

  return (
    <div className="mb-4">
      <div className="text-[13px] text-slate-600 mb-2 font-medium">联系人明细</div>
      <Table
        size="small"
        pagination={false}
        rowKey="_key"
        dataSource={rows}
        columns={columns}
        className="border border-slate-200 rounded-sm overflow-hidden"
      />
      <Button
        type="dashed"
        block
        className="mt-2"
        icon={<PlusOutlined />}
        onClick={() => onChange([...rows, emptyContactRow()])}
      >
        添加联系人
      </Button>
    </div>
  )
}

export function hasContactContent(rows: ContactDraftRow[]) {
  return rows.some((r) => (r.name || '').trim() || (r.phone || '').trim())
}
