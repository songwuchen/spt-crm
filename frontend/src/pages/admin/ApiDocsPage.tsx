import { useState } from 'react'
import { Radio, Collapse, Tag } from 'antd'
import { usePageTitle } from '@/hooks/usePageTitle'

const apiGroups = [
  {
    title: '认证', tag: 'auth', endpoints: [
      { method: 'POST', path: '/api/v1/auth/login', desc: '登录获取 JWT Token' },
      { method: 'POST', path: '/api/v1/auth/refresh', desc: '刷新 Token' },
      { method: 'GET', path: '/api/v1/auth/me', desc: '当前用户信息' },
      { method: 'PUT', path: '/api/v1/auth/profile', desc: '更新个人资料' },
      { method: 'POST', path: '/api/v1/auth/change-password', desc: '修改密码' },
      { method: 'GET', path: '/api/v1/auth/login-history', desc: '登录历史' },
    ],
  },
  {
    title: '客户', tag: 'customer', endpoints: [
      { method: 'GET', path: '/api/v1/customers', desc: '客户列表（支持 keyword、level、region 筛选）' },
      { method: 'POST', path: '/api/v1/customers', desc: '创建客户' },
      { method: 'GET', path: '/api/v1/customers/:id', desc: '客户详情' },
      { method: 'PUT', path: '/api/v1/customers/:id', desc: '更新客户' },
      { method: 'DELETE', path: '/api/v1/customers/:id', desc: '删除客户（级联保护）' },
      { method: 'GET', path: '/api/v1/customers/pool', desc: '公海客户列表' },
      { method: 'POST', path: '/api/v1/customers/:id/claim', desc: '领取客户' },
      { method: 'POST', path: '/api/v1/customers/:id/release', desc: '释放到公海' },
      { method: 'POST', path: '/api/v1/customers/batch_transfer', desc: '批量转移负责人' },
    ],
  },
  {
    title: '线索', tag: 'lead', endpoints: [
      { method: 'GET', path: '/api/v1/leads', desc: '线索列表（支持 keyword、status 筛选）' },
      { method: 'POST', path: '/api/v1/leads', desc: '创建线索' },
      { method: 'GET', path: '/api/v1/leads/:id', desc: '线索详情' },
      { method: 'PUT', path: '/api/v1/leads/:id', desc: '更新线索' },
      { method: 'POST', path: '/api/v1/leads/batch_assign', desc: '批量分配负责人' },
      { method: 'POST', path: '/api/v1/leads/batch_status', desc: '批量更新状态' },
    ],
  },
  {
    title: '任务', tag: 'task', endpoints: [
      { method: 'GET', path: '/api/v1/tasks', desc: '任务列表' },
      { method: 'POST', path: '/api/v1/tasks', desc: '创建任务' },
      { method: 'PUT', path: '/api/v1/tasks/:id', desc: '更新任务' },
      { method: 'DELETE', path: '/api/v1/tasks/:id', desc: '删除任务' },
      { method: 'POST', path: '/api/v1/tasks/batch_assign', desc: '批量指派' },
      { method: 'POST', path: '/api/v1/tasks/batch_complete', desc: '批量完成' },
    ],
  },
  {
    title: '商机项目', tag: 'project', endpoints: [
      { method: 'GET', path: '/api/v1/projects', desc: '商机列表' },
      { method: 'POST', path: '/api/v1/projects', desc: '创建商机' },
      { method: 'POST', path: '/api/v1/projects/:id/advance', desc: '推进阶段' },
    ],
  },
  {
    title: '审批', tag: 'approval', endpoints: [
      { method: 'POST', path: '/api/v1/approvals/submit', desc: '提交审批' },
      { method: 'POST', path: '/api/v1/approvals/:id/decide', desc: '审批决策' },
      { method: 'POST', path: '/api/v1/approvals/:id/withdraw', desc: '撤回审批' },
      { method: 'POST', path: '/api/v1/approvals/:id/delegate', desc: '委托审批' },
      { method: 'POST', path: '/api/v1/approvals/bulk_decide', desc: '批量审批' },
    ],
  },
  {
    title: '产品', tag: 'product', endpoints: [
      { method: 'GET', path: '/api/v1/products', desc: '产品列表（含引用次数）' },
      { method: 'GET', path: '/api/v1/products/categories', desc: '产品分类' },
      { method: 'GET', path: '/api/v1/products/check-unique', desc: '产品编码唯一性校验' },
    ],
  },
  {
    title: '工作台', tag: 'dashboard', endpoints: [
      { method: 'GET', path: '/api/v1/dashboard/stats', desc: '统计概览' },
      { method: 'GET', path: '/api/v1/dashboard/funnel', desc: '销售漏斗' },
      { method: 'GET', path: '/api/v1/dashboard/leaderboard', desc: '业绩排行' },
      { method: 'GET', path: '/api/v1/dashboard/collection', desc: '回款分析' },
      { method: 'GET', path: '/api/v1/dashboard/calendar_events', desc: '日历事件' },
    ],
  },
]

const methodColors: Record<string, string> = {
  GET: 'blue', POST: 'green', PUT: 'orange', DELETE: 'red',
}

export default function ApiDocsPage() {
  usePageTitle('API 文档')
  const [mode, setMode] = useState<'swagger' | 'redoc' | 'quick'>('quick')

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">API 文档</h1>
          <p className="text-sm text-slate-500 mt-0.5">接口文档与快速参考</p>
        </div>
        <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)} buttonStyle="solid" size="small">
          <Radio.Button value="quick">快速参考</Radio.Button>
          <Radio.Button value="swagger">Swagger UI</Radio.Button>
          <Radio.Button value="redoc">ReDoc</Radio.Button>
        </Radio.Group>
      </div>

      {mode === 'quick' ? (
        <div className="flex-1 overflow-y-auto bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="mb-4 bg-slate-50 rounded-lg p-4 border border-slate-200">
            <h3 className="text-sm font-bold text-slate-700 mb-2">认证方式</h3>
            <p className="text-sm text-slate-600">
              所有 API 请求需在 Header 中携带 <code className="bg-slate-200 px-1 rounded text-sm">Authorization: Bearer &lt;token&gt;</code>。
              通过 <code className="bg-slate-200 px-1 rounded text-sm">POST /api/v1/auth/login</code> 获取 Token。
            </p>
            <h3 className="text-sm font-bold text-slate-700 mt-3 mb-2">响应格式</h3>
            <pre className="text-sm bg-slate-100 p-3 rounded-lg overflow-x-auto">
{`{
  "code": 0,
  "message": "ok",
  "data": { ... }
}`}
            </pre>
            <p className="text-sm text-slate-500 mt-2">code=0 表示成功，非零为错误码。分页接口 data 包含 items, total, pageNo, pageSize。</p>
          </div>

          <Collapse
            defaultActiveKey={['auth']}
            items={apiGroups.map(g => ({
              key: g.tag,
              label: <span className="font-bold text-slate-800">{g.title}</span>,
              children: (
                <div className="space-y-1">
                  {g.endpoints.map((ep, i) => (
                    <div key={i} className="flex items-center gap-3 py-1.5 border-b border-slate-50 last:border-0">
                      <Tag color={methodColors[ep.method]} className="font-mono text-[12px] min-w-[50px] text-center">{ep.method}</Tag>
                      <code className="text-sm text-slate-700 font-mono flex-shrink-0">{ep.path}</code>
                      <span className="text-sm text-slate-500 ml-auto">{ep.desc}</span>
                    </div>
                  ))}
                </div>
              ),
            }))}
          />
        </div>
      ) : (
        <div className="flex-1 rounded-xl border border-slate-200 overflow-hidden bg-white shadow-sm">
          <iframe
            key={mode}
            src={mode === 'swagger' ? '/docs' : '/redoc'}
            className="w-full h-full border-0"
            title="API Documentation"
          />
        </div>
      )}
    </div>
  )
}
