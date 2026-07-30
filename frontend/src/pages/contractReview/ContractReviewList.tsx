import { useState, useEffect, useRef } from 'react'
import { Button, Input, Space, Select, Tag, Modal, message } from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import FillHeightTable from '@/components/list/FillHeightTable'
import { contractReviewApi, type ContractReview } from '@/api/contractReview'
import { CONTRACT_REVIEW_STATUS } from '@/constants/contractReview'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'

const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  CONTRACT_REVIEW_STATUS.map((s) => [s.value, s.label]),
)
const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  submitted: 'processing',
  approved: 'success',
  rejected: 'error',
}

const money = (v?: number | null) =>
  v != null ? `¥${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '-'

export default function ContractReviewList() {
  usePageTitle('合同评审')
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const canCreate = hasPermission('contract_review:create')
  const canDelete = hasPermission('contract_review:delete')

  const [data, setData] = useState<ContractReview[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>()
  const [reviewType, setReviewType] = useState<string | undefined>()
  const kwRef = useRef(keyword)
  kwRef.current = keyword

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await contractReviewApi.list({
        pageNo: p,
        pageSize,
        keyword: kwRef.current || undefined,
        status,
        review_type: reviewType,
      })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(1)
    setPage(1)
  }, [status, reviewType]) // eslint-disable-line react-hooks/exhaustive-deps

  const columns: ColumnsType<ContractReview> = [
    {
      title: '评审编号', dataIndex: 'review_code', width: 160,
      render: (v, r) => (
        <a className="text-primary font-bold" onClick={() => navigate(`/contract-reviews/${r.id}`)}>{v}</a>
      ),
    },
    { title: '类型', dataIndex: 'review_type', width: 100 },
    { title: '公司名称', dataIndex: 'company_name', ellipsis: true },
    { title: '项目', dataIndex: 'project_title', ellipsis: true, width: 180 },
    {
      title: '合同价格', dataIndex: 'contract_amount', width: 120,
      render: (v) => money(v),
    },
    { title: '业务员', dataIndex: 'owner_name', width: 90 },
    {
      title: '状态', dataIndex: 'status', width: 90,
      render: (v: string) => <Tag color={STATUS_COLOR[v] || 'default'}>{STATUS_LABEL[v] || v}</Tag>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 110,
      render: (v?: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-',
    },
    {
      title: '', key: 'actions', width: 120, fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          <a className="text-primary text-sm px-2" onClick={() => navigate(`/contract-reviews/${r.id}`)}>详情</a>
          {canDelete && (
            <a className="text-rose-500 text-sm px-2" onClick={() => {
              Modal.confirm({
                title: '确认删除',
                content: `确定删除合同评审「${r.review_code}」？`,
                okType: 'danger',
                onOk: async () => {
                  await contractReviewApi.delete(r.id)
                  message.success('已删除')
                  fetchData(page)
                },
              })
            }}>删除</a>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h2 className="text-xl font-semibold m-0">合同评审</h2>
        {canCreate && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/contract-reviews/new')}>
            新建评审
          </Button>
        )}
      </div>
      <div className="flex flex-wrap gap-2 mb-4">
        <Input
          allowClear
          placeholder="编号/公司/项目/业务员"
          prefix={<SearchOutlined />}
          className="w-64"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={() => { setPage(1); fetchData(1) }}
        />
        <Select
          allowClear
          placeholder="状态"
          className="w-32"
          options={[...CONTRACT_REVIEW_STATUS]}
          value={status}
          onChange={setStatus}
        />
        <Select
          allowClear
          placeholder="类型"
          className="w-36"
          options={[
            { value: '合同评审', label: '合同评审' },
            { value: '项目评审', label: '项目评审' },
          ]}
          value={reviewType}
          onChange={setReviewType}
        />
        <Button onClick={() => { setPage(1); fetchData(1) }}>查询</Button>
      </div>
      <FillHeightTable
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={data}
        pagination={{
          current: page,
          pageSize,
          total,
          onChange: (p) => { setPage(p); fetchData(p) },
        }}
      />
    </div>
  )
}
