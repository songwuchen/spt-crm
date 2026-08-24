import { useCallback, useEffect, useState } from 'react'

import { Button, Dropdown, Space, Table, Tag } from 'antd'

import type { MenuProps } from 'antd'

import { DownOutlined, PlusOutlined } from '@ant-design/icons'

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



export default function OpportunitySchemeFormsPanel({ projectId, onCountChange }: Props) {

  const { hasPermission } = usePermission()

  const canCreate = hasPermission('form_data:create')

  const [loading, setLoading] = useState(false)

  const [items, setItems] = useState<ProjectSchemeFormItem[]>([])

  const [modal, setModal] = useState<ModalState | null>(null)



  const load = useCallback(async () => {

    if (!projectId) return

    setLoading(true)

    try {

      const res = await projectApi.schemeForms(projectId)

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



  const openCreate = (templateCode: string, prefill: Record<string, unknown>) => {

    setModal({ mode: 'create', templateCode, prefillFormData: prefill })

  }



  const openView = (row: ProjectSchemeFormItem) => {

    setModal({ mode: 'view', templateCode: row.template_code, instanceId: row.id })

  }



  const createMenu: MenuProps['items'] = [

    {

      key: 'drawing-requisition',

      label: '合同图纸领用',

      onClick: () => openCreate('drawing_requisition', {}),

    },

    {

      key: 'install-notice',

      label: '安装图设计通知',

      onClick: () => openCreate('install_drawing_notice', { project_no: projectId }),

    },

    {

      key: 'presale-notice',

      label: '售前服务通知',

      onClick: () => openCreate('presale_service_notice', {}),

    },

  ]



  return (

    <div className="pb-6">

      <div className="flex justify-end mb-3 gap-2">

        {canCreate && (

          <Dropdown menu={{ items: createMenu }} trigger={['click']}>

            <Button type="primary" size="small" icon={<PlusOutlined />}>

              新建 <DownOutlined />

            </Button>

          </Dropdown>

        )}

      </div>

      <Table

        rowKey="id"

        size="small"

        loading={loading}

        dataSource={items}

        pagination={false}

        locale={{ emptyText: '暂无方案 / 图纸单据，可点击「新建」发起' }}

        columns={[

          {

            title: '流水号',

            dataIndex: 'serial_no',

            width: 150,

            render: (v: string, r: ProjectSchemeFormItem) => (

              <a className="font-mono font-bold text-primary" onClick={() => openView(r)}>

                {v || r.business_no || '—'}

              </a>

            ),

          },

          {

            title: '类型',

            dataIndex: 'kind_label',

            width: 180,

            ellipsis: true,

            render: (v: string, r: ProjectSchemeFormItem) => (

              <Tag color={r.template_code === 'install_drawing_notice' ? 'purple'

                : r.template_code === 'drawing_requisition' ? 'blue'

                  : r.subtype === 'install' ? 'geekblue' : 'blue'}>

                {v || r.template_name}

              </Tag>

            ),

          },

          {

            title: '设计卡号',

            dataIndex: 'design_card_no',

            width: 120,

            ellipsis: true,

            render: (v: string) => v || '—',

          },

          {

            title: '客户/事项',

            key: 'matter',

            ellipsis: true,

            render: (_: unknown, r: ProjectSchemeFormItem) => {

              const parts = [r.customer_name, r.matter].filter(Boolean)

              return parts.length ? parts.join(' · ') : '—'

            },

          },

          {

            title: '合同号',

            dataIndex: 'contract_no',

            width: 140,

            ellipsis: true,

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


