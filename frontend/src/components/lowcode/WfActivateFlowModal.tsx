/** 激活已结束流程：选择开始/审批节点后重开（对齐简道云「激活流程」）。 */
import { useEffect, useState } from 'react'
import { Modal, Select, message } from 'antd'
import { workflowApi } from '@/api/lowcodeWorkflow'

export type ActivateNodeOption = { id: string; name: string; type?: string }

export function WfActivateFlowModal({
  open,
  instanceId,
  nodes,
  onClose,
  onDone,
}: {
  open: boolean
  instanceId: string | null | undefined
  /** 若详情已带 activate_nodes 可直接传入，否则打开时拉取 */
  nodes?: ActivateNodeOption[] | null
  onClose: () => void
  onDone?: () => void
}) {
  const [options, setOptions] = useState<ActivateNodeOption[]>([])
  const [nodeId, setNodeId] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !instanceId) return
    let cancelled = false
    const run = async () => {
      if (nodes && nodes.length) {
        setOptions(nodes)
        setNodeId(nodes[0]?.id)
        return
      }
      setLoading(true)
      try {
        const res = await workflowApi.activateNodes(instanceId)
        if (cancelled) return
        const list = res.data || []
        setOptions(list)
        setNodeId(list[0]?.id)
      } catch {
        if (!cancelled) message.error('加载可激活节点失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void run()
    return () => { cancelled = true }
  }, [open, instanceId, nodes])

  const handleOk = async () => {
    if (!instanceId) return
    if (!nodeId) {
      message.error('请选择激活节点')
      return
    }
    setBusy(true)
    try {
      await workflowApi.activate(instanceId, { to_node_id: nodeId })
      message.success('流程已激活')
      onClose()
      onDone?.()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '激活失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title="激活流程"
      open={open}
      onCancel={onClose}
      onOk={() => void handleOk()}
      okText="确认激活"
      confirmLoading={busy}
      destroyOnClose
      width={420}
    >
      <div className="space-y-2 py-2">
        <div className="text-sm text-slate-500">选择激活节点</div>
        <Select
          className="w-full"
          loading={loading}
          placeholder="选择激活节点"
          value={nodeId}
          onChange={setNodeId}
          showSearch
          optionFilterProp="label"
          options={options.map((n) => ({
            value: n.id,
            label: n.name,
          }))}
        />
      </div>
    </Modal>
  )
}

export default WfActivateFlowModal
