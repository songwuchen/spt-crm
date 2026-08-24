import { useCallback, useEffect, useState } from 'react'
import { Button, Space, Table, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { projectApi, type ProjectSchemeFormItem } from '@/api/project'
import EmbeddedLowcodeFormModal, { type EmbeddedLowcodeFormModalProps } from '@/components/lowcode/EmbeddedLowcodeFormModal'
import { usePermission } from '@/hooks/usePermission'

const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  submitted: 'blue',
  running: 'gold',
  completed: 'green',
  rejected: 'red',
  withdrawn: 'default',
}

type ModalState = Pick<EmbeddedLowcodeFormModalProps, 'mode' | 'templateCode' | 'instanceId' | 'prefillFormData'>

type Props = {
  projectId: string
  onCountChange?: (n: number) => void
}

export default function OpportunityQuoteFormsPanel({ projectId, onCountChange }: Props) {
  const { hasPermission } = usePermission()
  const canCreate = hasPermission('form_data:create')
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<ProjectSchemeFormItem[]>([])
  const [modal, setModal] = useState<ModalState | null>(null)

  const load = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const res = await projectApi.quoteForms(projectId)
      const list = res.data?.items || []
      setItems(list)
      onCountChange?.(list.length)
    } catch {
      setItems([])
      onCountChange?.(0)
    } finally {
      setLoading(false)
    }
  }, [projectId, onCountChange])

  useEffect(() => { void load() }, [load])

  const openView = (row: ProjectSchemeFormItem) => {
    setModal({ mode: 'view', templateCode: row.template_code, instanceId: row.id })
  }

  return (
    <div className="pb-6">
      <div className="flex justify-end mb-3 gap-2">
        {canCreate && (
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => setModal({
              mode: 'create',
              templateCode: 'quote_management',
              prefillFormData: { related_project: projectId },
            })}
          >
            新建报价
          </Button>
        )}
      </div>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        dataSource={items}
        pagination={false}
        locale={{ emptyText: '暂无报价单，可点击「新建报价」发起核价流程' }}
        columns={[
          {
            title: '流水号',
            dataIndex: 'serial_no',
            width: 140,
            render: (v: string, r: ProjectSchemeFormItem) => (
              <a className="font-mono font-bold text-primary" onClick={() => openView(r)}>
                {v || r.business_no || '—'}
              </a>
            ),
          },
          {
            title: '客户名称',
            dataIndex: 'customer_name',
            ellipsis: true,
            render: (v: string) => v || '—',
          },
          {
            title: '参考合同号',
            dataIndex: 'ref_contract_no',
            width: 130,
            ellipsis: true,
            render: (v: string, r: ProjectSchemeFormItem) => v || r.contract_no || '—',
          },
          {
            title: '价格类型',
            dataIndex: 'price_type',
            width: 100,
            render: (v: string) => v || '—',
          },
          {
            title: '客户类别',
            dataIndex: 'customer_category',
            width: 100,
            render: (v: string) => v || '—',
          },
          {
            title: '需采购',
            dataIndex: 'need_purchase',
            width: 80,
            render: (v: string) => v || '—',
          },
          {
            title: '状态',
            dataIndex: 'status',
            width: 90,
            render: (v: string, r: ProjectSchemeFormItem) => (
              <Tag color={STATUS_COLORS[v] || 'default'}>{r.status_label || v}</Tag>
            ),
          },
          {
            title: '提交人',
            dataIndex: 'initiator_name',
            width: 90,
            render: (v: string) => v || '—',
          },
          {
            title: '创建时间',
            dataIndex: 'created_at',
            width: 110,
            render: (v: string) => (v ? new Date(v).toLocaleDateString('zh-CN') : '—'),
          },
          {
            title: '',
            key: 'actions',
            width: 60,
            render: (_: unknown, r: ProjectSchemeFormItem) => (
              <Space size={4}>
                <a className="text-primary text-sm font-bold" onClick={() => openView(r)}>查看</a>
              </Space>
            ),
          },
        ]}
      />

      {modal && (
        <EmbeddedLowcodeFormModal
          open
          mode={modal.mode}
          templateCode={modal.templateCode}
          instanceId={modal.instanceId}
          prefillFormData={modal.prefillFormData}
          onClose={() => setModal(null)}
          onDone={() => { void load() }}
        />
      )}
    </div>
  )
}
