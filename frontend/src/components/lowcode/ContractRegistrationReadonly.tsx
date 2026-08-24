/** 审批抽屉内只读展示合同登记全部分区（复用详情页字段定义） */
import { Descriptions, Tag, Typography } from 'antd'
import type { ContractItem, ContractVersion } from '@/api/types'
import {
  CONTRACT_REGISTRATION_SECTIONS,
  formatChangeType,
  formatRegFieldValue,
  type RegFieldDef,
} from '@/constants/contractRegistration'
import { PaymentTermsView, ClauseTermsView } from '@/components/ContractTerms'
import ContractAttachmentSlots from '@/components/ContractAttachmentSlots'

const { Text } = Typography

function formatMoney(v: number | string) {
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return String(v)
  return `¥${n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div className="text-sm font-semibold text-slate-700 mb-2 pb-1 border-b border-slate-100">
      {title}
    </div>
  )
}

export default function ContractRegistrationReadonly({
  contract,
  version,
}: {
  contract: ContractItem
  version?: ContractVersion | null
}) {
  const reg = (contract.registration_json || {}) as Record<string, unknown>

  const depOk = (f: RegFieldDef) => {
    if (!f.showWhen) return true
    const sw = f.showWhen
    const raw = (sw.source || 'reg') === 'native'
      ? (contract as unknown as Record<string, unknown>)[sw.field]
      : reg[sw.field]
    if (!sw.equals?.length) return raw != null && raw !== ''
    return sw.equals.includes(raw == null ? '' : String(raw))
  }

  const resolve = (f: RegFieldDef) => {
    if (f.key === 'assignee_id') return contract.assignee_name || contract.assignee_id || '-'
    if (f.key === 'department_id') return contract.department_name || contract.department_id || '-'
    if (f.key === 'customer_id') return contract.customer_name || contract.customer_id || '-'
    const raw = f.source === 'native'
      ? (contract as unknown as Record<string, unknown>)[f.key]
      : reg[f.key]
    if (f.key === 'amount_total') return raw != null && raw !== '' ? formatMoney(raw as number | string) : '-'
    if (f.key === 'change_type') return formatChangeType(raw as string)
    if (typeof raw === 'number' && (f.widget === 'money' || f.key.includes('amount'))) {
      return formatMoney(raw)
    }
    // 人员/部门对象或数组（简道云同步可能带 name）
    if (Array.isArray(raw) && raw.some((x) => x && typeof x === 'object')) {
      return raw.map((x) => {
        if (x && typeof x === 'object') {
          const o = x as Record<string, unknown>
          return String(o.name || o.label || o.username || o.id || '')
        }
        return String(x)
      }).filter(Boolean).join('、') || '-'
    }
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      const o = raw as Record<string, unknown>
      return String(o.name || o.label || o.username || o.id || '-')
    }
    return formatRegFieldValue(f, raw)
  }

  const renderDesc = (fields: RegFieldDef[]) => {
    const visible = fields.filter((f) => depOk(f))
    if (!visible.length) return null
    return (
      <Descriptions size="small" column={2} bordered className="mb-3 text-sm">
        {visible.map((f) => {
          const value = resolve(f)
          return (
            <Descriptions.Item key={f.key} label={f.label}>
              {f.key === 'amount_total' && value !== '-' ? (
                <span className="font-bold">{value}</span>
              ) : f.key === 'change_type' && value !== '-' ? (
                <Tag>{value}</Tag>
              ) : (
                value
              )}
            </Descriptions.Item>
          )
        })}
      </Descriptions>
    )
  }

  return (
    <div className="space-y-5">
      {CONTRACT_REGISTRATION_SECTIONS.map((sec) => (
        <div key={sec.key}>
          <SectionTitle title={sec.title} />
          {renderDesc(sec.fields)}
          {sec.afterSlot === 'line_items' && (
            <div className="mb-3">
              <Text type="secondary" className="text-xs block mb-1">合同明细</Text>
              <ClauseTermsView value={version?.key_clauses_json} />
            </div>
          )}
          {sec.afterSlot === 'payment_terms' && (
            <div className="mb-3">
              <Text type="secondary" className="text-xs block mb-1">收款计划</Text>
              {contract.payment_terms_json
                ? <PaymentTermsView value={contract.payment_terms_json} />
                : <div className="text-sm text-slate-400">暂无收款计划</div>}
            </div>
          )}
          {sec.afterSlot === 'contract_files' && (
            <div className="mb-3">
              <ContractAttachmentSlots slot="contract_files" contractId={contract.id} />
            </div>
          )}
          {sec.afterSlot === 'accept_files' && (
            <div className="mb-3">
              <ContractAttachmentSlots slot="accept_files" contractId={contract.id} />
            </div>
          )}
          {sec.fieldsAfterSlot?.length ? renderDesc(sec.fieldsAfterSlot) : null}
        </div>
      ))}
      {version?.risk_level && (
        <div>
          <SectionTitle title="版本信息" />
          <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="版本号">V{version.version_no}</Descriptions.Item>
            <Descriptions.Item label="风险等级">{version.risk_level}</Descriptions.Item>
            <Descriptions.Item label="版本状态">{version.status}</Descriptions.Item>
            <Descriptions.Item label="版本标题">{version.title || '-'}</Descriptions.Item>
          </Descriptions>
        </div>
      )}
    </div>
  )
}
