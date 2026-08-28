/**
 * 商机等业务页内嵌：低代码表单新建 / 查看弹窗（不跳转侧栏模块页）。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button, Modal, Spin, message } from 'antd'
import { EditOutlined, SendOutlined } from '@ant-design/icons'
import { lowcodeApi } from '@/api/lowcode'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { FieldDefinition, FormRule, WfInstanceDetail } from '@/types/lowcode'
import FormRenderer, { deriveRolePerms, findRequiredError, scrollToLcField } from '@/components/lowcode/FormRenderer'
import FormFillPage from '@/pages/lowcode/FormFillPage'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import FormInstanceSystemMeta from '@/components/lowcode/FormInstanceSystemMeta'
import { buildFormFieldLabels } from '@/utils/dataLogLabels'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'
import { DRAWING_FORM_LAYOUT, applyDrawingFormLayout } from '@/constants/drawingFormLayout'
import { useAuthStore } from '@/stores/useAuthStore'

const TEMPLATE_LABELS: Record<string, string> = {
  drawing_requisition: '合同图纸领用',
  install_drawing_notice: '安装图设计通知',
  presale_service_notice: '售前服务通知',
  quote_management: '报价管理',
  scheme_management: '方案管理',
}

type ViewRec = {
  fields: FieldDefinition[]
  value: Record<string, unknown>
  readonly: boolean
  id: string
  process_instance_id?: string | null
  rules: FormRule[]
  status?: string
  initiator_name?: string | null
  created_at?: string
  updated_at?: string | null
}

export type EmbeddedLowcodeFormModalProps = {
  open: boolean
  onClose: () => void
  onDone?: () => void
  mode: 'create' | 'view'
  templateCode: string
  title?: string
  instanceId?: string
  prefillFormData?: Record<string, unknown>
}

function canEditRecord(templateCode: string, status?: string | null) {
  const postCompleteEditable = templateCode === 'drawing_requisition'
    || templateCode === 'install_drawing_notice'
    || templateCode === 'cs_drawing_request'
  return status === 'draft' || status === 'rejected' || status === 'returned'
    || (postCompleteEditable && status === 'completed')
}

function canResubmitRecord(status?: string | null) {
  return status === 'draft' || status === 'rejected' || status === 'returned'
}

export default function EmbeddedLowcodeFormModal({
  open,
  onClose,
  onDone,
  mode,
  templateCode,
  title,
  instanceId,
  prefillFormData,
}: EmbeddedLowcodeFormModalProps) {
  const userRoles = useAuthStore((s) => s.user?.roles) || []
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [bootLoading, setBootLoading] = useState(false)
  const [viewRec, setViewRec] = useState<ViewRec | null>(null)
  const [wfDetail, setWfDetail] = useState<WfInstanceDetail | null>(null)
  const [wfCommenting, setWfCommenting] = useState(false)
  const [viewLoading, setViewLoading] = useState(false)

  const displayTitle = title || TEMPLATE_LABELS[templateCode] || templateCode
  const layout = DRAWING_FORM_LAYOUT[templateCode]
  const contentMaxWidth = layout?.contentMaxWidth ?? 760

  const loadWorkflow = useCallback(async (recId: string, processInstanceId?: string | null) => {
    try {
      if (processInstanceId) {
        const res = await workflowApi.instance(processInstanceId)
        setWfDetail(res.data || null)
        return
      }
      const res = await workflowApi.byFormInstance({ form_instance_id: recId })
      setWfDetail(res.data || null)
    } catch {
      setWfDetail(null)
    }
  }, [])

  const loadView = useCallback(async (recId: string, readonly = true) => {
    setViewLoading(true)
    try {
      const res = await lowcodeApi.getInstance(recId)
      const detailRules = (res.data.rule_definitions as FormRule[] | undefined)
      setViewRec({
        fields: res.data.field_definitions,
        value: res.data.form_data,
        readonly,
        id: recId,
        process_instance_id: res.data.process_instance_id,
        rules: detailRules || [],
        status: res.data.status,
        initiator_name: res.data.initiator_name,
        created_at: res.data.created_at,
        updated_at: res.data.updated_at,
      })
      setWfDetail(null)
      await loadWorkflow(recId, res.data.process_instance_id)
    } catch {
      message.error('加载单据失败')
      onClose()
    } finally {
      setViewLoading(false)
    }
  }, [loadWorkflow, onClose])

  useEffect(() => {
    if (!open) {
      setTemplateId(null)
      setViewRec(null)
      setWfDetail(null)
      return
    }
    let cancelled = false
    setBootLoading(true)
    ;(async () => {
      try {
        const res = await lowcodeApi.ensureBuiltin(templateCode)
        if (cancelled) return
        setTemplateId(res.data.id)
        if (mode === 'view' && instanceId) {
          await loadView(instanceId, true)
        }
      } catch {
        if (!cancelled) {
          message.error('加载表单失败')
          onClose()
        }
      } finally {
        if (!cancelled) setBootLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [open, mode, templateCode, instanceId, loadView, onClose])

  const displayFields = useMemo(() => {
    if (!viewRec) return []
    return layout ? applyDrawingFormLayout(templateCode, viewRec.fields) : viewRec.fields
  }, [viewRec, layout, templateCode])

  const postCompleteEditable = templateCode === 'drawing_requisition'
    || templateCode === 'install_drawing_notice'
    || templateCode === 'cs_drawing_request'
    || templateCode === 'prod_card_supplement'
  const includeApproverFieldsOnEdit = Boolean(
    viewRec && !viewRec.readonly && postCompleteEditable
      && (templateCode === 'prod_card_supplement' || viewRec.status === 'completed'),
  )

  const handleClose = () => {
    setViewRec(null)
    setWfDetail(null)
    onClose()
  }

  const handleDone = () => {
    onDone?.()
    handleClose()
  }

  const saveEdit = async () => {
    if (!viewRec) return
    try {
      await lowcodeApi.updateInstance(viewRec.id, { form_data: viewRec.value })
      message.success('已保存')
      handleDone()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '保存失败')
    }
  }

  const submitDraft = async () => {
    if (!viewRec) return
    const states = computeFieldStates(
      displayFields, viewRec.value, viewRec.rules,
      deriveRolePerms(displayFields, userRoles),
    )
    const e = findRequiredError(displayFields, states, viewRec.value, viewRec.rules)
    if (e) {
      message.error(e.message)
      scrollToLcField(e.fieldId)
      return
    }
    try {
      await lowcodeApi.submitInstance(viewRec.id, { form_data: viewRec.value })
      message.success('已提交审批')
      handleDone()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '提交失败')
    }
  }

  const handleWfComment = async (content: string) => {
    if (!wfDetail?.id || !viewRec) return
    setWfCommenting(true)
    try {
      await workflowApi.comment(wfDetail.id, content)
      message.success('评论已发表')
      await loadWorkflow(viewRec.id, wfDetail.id)
    } catch {
      message.error('发表评论失败')
    } finally {
      setWfCommenting(false)
    }
  }

  const modalWidth = mode === 'view' ? Math.max(980, contentMaxWidth + 320) : Math.max(860, contentMaxWidth + 40)
  const showFlowPane = mode === 'view' && !!viewRec

  const viewFooter = viewRec && !viewRec.readonly && canEditRecord(templateCode, viewRec.status)
    ? [
        <Button key="c" onClick={handleClose}>取消</Button>,
        <Button
          key="s"
          type={canResubmitRecord(viewRec.status) ? 'default' : 'primary'}
          onClick={saveEdit}
        >
          {canResubmitRecord(viewRec.status) ? '存草稿' : '保存'}
        </Button>,
        ...(canResubmitRecord(viewRec.status)
          ? [<Button key="sub" type="primary" onClick={submitDraft}>提交审批</Button>]
          : []),
      ]
    : [<Button key="c" onClick={handleClose}>关闭</Button>]

  return (
    <Modal
      title={mode === 'create' ? `新建 · ${displayTitle}` : `查看 · ${displayTitle}`}
      open={open}
      onCancel={handleClose}
      footer={mode === 'create' ? null : viewFooter}
      width={modalWidth}
      destroyOnClose
      styles={{ body: { maxHeight: '72vh', overflowY: 'auto' } }}
    >
      {bootLoading || (mode === 'view' && viewLoading && !viewRec) ? (
        <div className="flex justify-center py-16">
          <Spin />
        </div>
      ) : mode === 'create' && templateId ? (
        <FormFillPage
          templateId={templateId}
          templateCode={templateCode}
          embedded
          prefillFormData={prefillFormData}
          onSuccess={handleDone}
          onCancel={handleClose}
        />
      ) : viewRec ? (
        <div>
          <div className="flex items-center gap-1 mb-3 px-1 py-1 border-b border-slate-100">
            {canEditRecord(templateCode, viewRec.status) && viewRec.readonly && (
              <Button
                type="text"
                icon={<EditOutlined />}
                onClick={() => setViewRec((s) => (s ? { ...s, readonly: false } : s))}
              >
                编辑
              </Button>
            )}
            {canResubmitRecord(viewRec.status) && viewRec.readonly && (
              <Button type="text" icon={<SendOutlined />} onClick={submitDraft}>
                提交审批
              </Button>
            )}
          </div>
          <div className="flex gap-0 min-h-[420px]">
            <div className="flex-1 overflow-y-auto pr-3">
              <FormRenderer
                fields={displayFields}
                rules={viewRec.rules}
                mode={viewRec.readonly ? 'readonly' : 'edit'}
                value={viewRec.value}
                onChange={(v) => setViewRec((s) => (s ? { ...s, value: v } : s))}
                includeApproverFields={includeApproverFieldsOnEdit}
              />
              <FormInstanceSystemMeta
                initiatorName={viewRec.initiator_name}
                createdAt={viewRec.created_at}
                updatedAt={viewRec.updated_at}
                status={viewRec.status}
                flowSteps={wfDetail?.flow_steps}
              />
            </div>
            {showFlowPane && (
              <div className="w-[280px] shrink-0 overflow-hidden rounded-md border border-slate-200 max-h-[65vh]">
                <WfFlowDynamics
                  steps={wfDetail?.flow_steps || []}
                  comments={wfDetail?.comments || []}
                  onSubmitComment={wfDetail ? handleWfComment : undefined}
                  commenting={wfCommenting}
                  dataLog={{
                    resourceType: 'form_instance',
                    resourceId: viewRec.id,
                    fieldLabels: buildFormFieldLabels(viewRec.fields),
                    alsoResources: wfDetail?.id
                      ? [{ resourceType: 'wf_process_instance', resourceId: wfDetail.id }]
                      : undefined,
                  }}
                />
              </div>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  )
}
