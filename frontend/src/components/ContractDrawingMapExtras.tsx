/** 合同图纸对应表填报：对齐简道云「最近一条查看」+「查询合同登记」 */
import { useEffect, useState } from 'react'
import { Avatar, Empty, Table, Tag } from 'antd'
import dayjs from 'dayjs'
import client from '@/api/client'
import { contractApi } from '@/api/contract'
import { lowcodeApi } from '@/api/lowcode'
import type { ApiResponse, ContractItem, PageData } from '@/api/types'
import type { FormInstance } from '@/types/lowcode'
import {
  contractDisplayStatusColors,
  contractDisplayStatusLabels,
  resolveContractDisplayStatus,
} from '@/constants/labels'

type Props = {
  templateId: string
  contractNo: string
  /** 提交成功后递增，刷新「最近一条」 */
  refreshKey?: number
}

function fmtMoney(v: unknown): string {
  if (v == null || v === '') return '—'
  const n = typeof v === 'number' ? v : Number(String(v).replace(/,/g, ''))
  if (!Number.isFinite(n)) return String(v)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

export default function ContractDrawingMapExtras({
  templateId,
  contractNo,
  refreshKey = 0,
}: Props) {
  const [recent, setRecent] = useState<{
    contract_no: string
    drawing_no: string
    submitter: string
    created_at: string
  } | null>(null)
  const [contracts, setContracts] = useState<ContractItem[]>([])
  const [loadingContracts, setLoadingContracts] = useState(false)

  useEffect(() => {
    if (!templateId) return
    let alive = true
    ;(async () => {
      try {
        const res = await lowcodeApi.listInstances({
          template_id: templateId,
          pageNo: 1,
          pageSize: 1,
        })
        const item = (res.data?.items || [])[0] as FormInstance | undefined
        if (!alive || !item) {
          if (alive) setRecent(null)
          return
        }
        const fd = item.form_data || {}
        let name = ''
        if (item.initiator_id) {
          try {
            const lr = await client.get<unknown, ApiResponse<Record<string, string>>>(
              '/api/v1/lc/person-labels',
              { params: { ids: item.initiator_id } },
            )
            name = (lr.data?.[item.initiator_id] || '').trim()
          } catch { /* ignore */ }
        }
        if (!alive) return
        setRecent({
          contract_no: String(fd.contract_no || '—'),
          drawing_no: String(fd.drawing_no || item.business_no || '—'),
          submitter: name || '—',
          created_at: item.created_at
            ? dayjs(item.created_at).format('YYYY-MM-DD HH:mm:ss')
            : '—',
        })
      } catch {
        if (alive) setRecent(null)
      }
    })()
    return () => { alive = false }
  }, [templateId, refreshKey])

  useEffect(() => {
    const kw = (contractNo || '').trim()
    if (!kw) {
      setContracts([])
      return
    }
    let alive = true
    setLoadingContracts(true)
    const t = window.setTimeout(() => {
      ;(async () => {
        try {
          const res = await contractApi.list({
            keyword: kw,
            pageNo: 1,
            pageSize: 20,
          })
          const page = res.data as PageData<ContractItem> | ContractItem[] | undefined
          const items = Array.isArray(page)
            ? page
            : ((page as PageData<ContractItem> | undefined)?.items || [])
          if (alive) setContracts(items)
        } catch {
          if (alive) setContracts([])
        } finally {
          if (alive) setLoadingContracts(false)
        }
      })()
    }, 280)
    return () => {
      alive = false
      window.clearTimeout(t)
    }
  }, [contractNo])

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
        <div className="mb-2 text-sm font-semibold text-slate-800">最近一条查看</div>
        {recent ? (
          <div className="flex flex-wrap items-center gap-x-8 gap-y-2 text-sm text-slate-700">
            <span>
              <span className="text-slate-500">合同号：</span>
              {recent.contract_no}
            </span>
            <span>
              <span className="text-slate-500">图纸编号：</span>
              {recent.drawing_no}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="text-slate-500">提交人：</span>
              <Avatar size={22} className="bg-teal-600 text-[11px]">
                {(recent.submitter || '?').slice(0, 1)}
              </Avatar>
              {recent.submitter}
            </span>
            <span>
              <span className="text-slate-500">提交时间：</span>
              {recent.created_at}
            </span>
          </div>
        ) : (
          <div className="text-sm text-slate-400">暂无记录</div>
        )}
      </div>

      <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
        <div className="mb-2 text-sm font-semibold text-slate-800">查询合同登记</div>
        <Table
          size="small"
          rowKey="id"
          loading={loadingContracts}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  (contractNo || '').trim()
                    ? '未找到匹配的合同登记'
                    : '填写合同号后显示关联合同'
                }
              />
            ),
          }}
          dataSource={contracts}
          columns={[
            {
              title: '单位名称',
              dataIndex: 'customer_name',
              ellipsis: true,
              render: (v: string) => v || '—',
            },
            {
              title: '合同总金额',
              dataIndex: 'amount_total',
              width: 140,
              render: (v: unknown) => fmtMoney(v),
            },
            {
              title: '提交时间',
              dataIndex: 'created_at',
              width: 170,
              render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '—'),
            },
            {
              title: '流程状态',
              key: 'flow_status',
              width: 110,
              render: (_: unknown, row: ContractItem) => {
                const ds = resolveContractDisplayStatus(row.status, row.current_version_status)
                return (
                  <Tag color={contractDisplayStatusColors[ds] || 'default'}>
                    {contractDisplayStatusLabels[ds] || ds}
                  </Tag>
                )
              },
            },
          ]}
        />
      </div>
    </div>
  )
}
