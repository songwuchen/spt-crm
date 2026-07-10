import { useState, useEffect, useRef } from 'react'
import { Button, Form, Input, InputNumber, Switch, message, Alert, Spin, Divider, Tag, Progress } from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined,
  ApiOutlined, TeamOutlined, ApartmentOutlined, UserOutlined, LoginOutlined, BellOutlined,
} from '@ant-design/icons'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'

interface DingTalkConfig {
  app_key: string
  app_secret: string
  corp_id: string
  default_password: string
  root_dept_id: number
  login_enabled: boolean
  agent_id: string
  webhook_url: string
  secret: string
  crm_base_url: string
  crm_h5_base_url: string
  auto_sync: boolean
  sync_time: string
  last_sync_at?: string
  status: string
}

interface SyncDeptResult {
  created: number
  updated: number
  total: number
  leader_updated: number
}

interface SyncUserResult {
  created: number
  updated: number
  skipped: number
  total: number
  leader_updated: number
  failed: { userid: string; reason: string }[]
}

type SyncKind = 'dingtalk_departments' | 'dingtalk_users'
type SyncStatus = 'running' | 'completed' | 'failed'

interface SyncTaskStatus<R> {
  id: string
  kind: SyncKind
  status: SyncStatus
  phase: string
  processed: number
  total: number
  result: R | null
  error: string | null
  started_at: number
  finished_at: number | null
}

const api = {
  getConfig: () => client.get<unknown, ApiResponse<DingTalkConfig | null>>('/api/admin/v1/tenant/dingtalk/config'),
  saveConfig: (data: Partial<DingTalkConfig>) =>
    client.post<unknown, ApiResponse<{ saved: boolean }>>('/api/admin/v1/tenant/dingtalk/config', data),
  testConnection: () =>
    client.post<unknown, ApiResponse<{ connected: boolean; dept_count?: number; error?: string }>>('/api/admin/v1/tenant/dingtalk/test'),
  syncDepts: (syncLeaders = true) =>
    client.post<unknown, ApiResponse<{ task_id: string; reused: boolean }>>(`/api/admin/v1/tenant/dingtalk/sync/departments?sync_leaders=${syncLeaders}`),
  syncUsers: () =>
    client.post<unknown, ApiResponse<{ task_id: string; reused: boolean }>>('/api/admin/v1/tenant/dingtalk/sync/users'),
  taskStatus: <R,>(taskId: string) =>
    client.get<unknown, ApiResponse<SyncTaskStatus<R>>>(`/api/admin/v1/tenant/dingtalk/sync/tasks/${taskId}`),
  activeTask: (kind: SyncKind) =>
    client.get<unknown, ApiResponse<{ task_id: string | null }>>(`/api/admin/v1/tenant/dingtalk/sync/active?kind=${kind}`),
}

export default function DingTalkPage() {
  usePageTitle('钉钉集成')
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [syncingDepts, setSyncingDepts] = useState(false)
  const [syncingUsers, setSyncingUsers] = useState(false)
  const [lastSyncAt, setLastSyncAt] = useState('')

  const [testResult, setTestResult] = useState<{ connected: boolean; dept_count?: number; error?: string } | null>(null)
  const [deptResult, setDeptResult] = useState<SyncDeptResult | null>(null)
  const [userResult, setUserResult] = useState<SyncUserResult | null>(null)
  const [deptProgress, setDeptProgress] = useState<SyncTaskStatus<SyncDeptResult> | null>(null)
  const [userProgress, setUserProgress] = useState<SyncTaskStatus<SyncUserResult> | null>(null)

  // Track active poll timers so unmount/re-click cancels them cleanly
  const deptPollRef = useRef<number | null>(null)
  const userPollRef = useRef<number | null>(null)

  useEffect(() => {
    loadConfig()
    // Resume any sync left running from a previous page load (e.g. user refreshed mid-sync)
    ;(async () => {
      try {
        const [d, u] = await Promise.all([
          api.activeTask('dingtalk_departments'),
          api.activeTask('dingtalk_users'),
        ])
        if (d.data?.task_id) {
          setSyncingDepts(true)
          pollTask<SyncDeptResult>(d.data.task_id, 'dept')
        }
        if (u.data?.task_id) {
          setSyncingUsers(true)
          pollTask<SyncUserResult>(u.data.task_id, 'user')
        }
      } catch { /* silently ignore */ }
    })()
    return () => {
      if (deptPollRef.current) window.clearTimeout(deptPollRef.current)
      if (userPollRef.current) window.clearTimeout(userPollRef.current)
    }
  }, [])

  const pollTask = <R,>(taskId: string, target: 'dept' | 'user') => {
    const tick = async () => {
      try {
        const res = await api.taskStatus<R>(taskId)
        const t = res.data
        if (target === 'dept') setDeptProgress(t as SyncTaskStatus<SyncDeptResult>)
        else setUserProgress(t as SyncTaskStatus<SyncUserResult>)

        if (t.status === 'running') {
          const ref = target === 'dept' ? deptPollRef : userPollRef
          ref.current = window.setTimeout(tick, 1500)
          return
        }

        // Finished — commit result and stop loading
        if (target === 'dept') {
          setSyncingDepts(false)
          if (t.status === 'completed' && t.result) {
            const r = t.result as unknown as SyncDeptResult
            setDeptResult(r)
            message.success(`部门同步完成：新建 ${r.created}，更新 ${r.updated}`)
          } else {
            message.error(t.error || '同步部门失败')
          }
        } else {
          setSyncingUsers(false)
          if (t.status === 'completed' && t.result) {
            const r = t.result as unknown as SyncUserResult
            setUserResult(r)
            if (r.failed.length === 0) {
              message.success(`用户同步完成：新建 ${r.created}，更新 ${r.updated}`)
            } else {
              message.warning(`用户同步完成：新建 ${r.created}，更新 ${r.updated}，失败 ${r.failed.length}`)
            }
          } else {
            message.error(t.error || '同步用户失败')
          }
        }
      } catch (e: any) {
        // Task may have been GC'd or network blipped — stop polling and show the raw error
        if (target === 'dept') setSyncingDepts(false)
        else setSyncingUsers(false)
        message.error(e?.response?.data?.message || '查询同步状态失败')
      }
    }
    void tick()
  }

  const loadConfig = async () => {
    setLoading(true)
    try {
      const res = await api.getConfig()
      if (res.data) {
        form.setFieldsValue({
          app_key: res.data.app_key,
          app_secret: res.data.app_secret,
          corp_id: res.data.corp_id || '',
          default_password: res.data.default_password || 'Changeme@123',
          root_dept_id: res.data.root_dept_id || 1,
          login_enabled: res.data.login_enabled || false,
          agent_id: res.data.agent_id || '',
          webhook_url: res.data.webhook_url || '',
          secret: res.data.secret || '',
          crm_base_url: res.data.crm_base_url || '',
          crm_h5_base_url: res.data.crm_h5_base_url || '',
          auto_sync: res.data.auto_sync || false,
          sync_time: res.data.sync_time || '02:00',
        })
        setLastSyncAt(res.data.last_sync_at || '')
      }
    } catch {
      // no config yet
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      await api.saveConfig(values)
      message.success('配置已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await api.testConnection()
      setTestResult(res.data)
      if (res.data?.connected) {
        message.success(`连接成功，共 ${res.data.dept_count} 个部门`)
      } else {
        message.warning('连接失败')
      }
    } catch (e: any) {
      setTestResult({ connected: false, error: e?.response?.data?.message || '请求失败' })
    } finally {
      setTesting(false)
    }
  }

  const handleSyncDepts = async () => {
    setSyncingDepts(true)
    setDeptResult(null)
    setDeptProgress(null)
    try {
      const res = await api.syncDepts(true)
      if (res.data.reused) message.info('已有同步任务在运行，继续显示其进度')
      pollTask<SyncDeptResult>(res.data.task_id, 'dept')
    } catch (e: any) {
      setSyncingDepts(false)
      message.error(e?.response?.data?.message || '启动同步失败')
    }
  }

  const handleSyncUsers = async () => {
    setSyncingUsers(true)
    setUserResult(null)
    setUserProgress(null)
    try {
      const res = await api.syncUsers()
      if (res.data.reused) message.info('已有同步任务在运行，继续显示其进度')
      pollTask<SyncUserResult>(res.data.task_id, 'user')
    } catch (e: any) {
      setSyncingUsers(false)
      message.error(e?.response?.data?.message || '启动同步失败')
    }
  }

  const renderProgress = (t: SyncTaskStatus<unknown> | null) => {
    if (!t || t.status !== 'running') return null
    const pct = t.total > 0 ? Math.floor((t.processed / t.total) * 100) : 0
    return (
      <div className="mt-3">
        <div className="text-xs text-slate-500 mb-1">
          {t.phase}{t.total > 0 ? ` ${t.processed}/${t.total}` : ''}
        </div>
        <Progress percent={pct} status="active" size="small" />
      </div>
    )
  }

  if (loading) {
    return <div className="flex justify-center py-20"><Spin size="large" /></div>
  }

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">钉钉集成</h1>
        <p className="text-sm text-slate-500 mt-0.5">配置企业内部应用凭证，同步钉钉的部门与用户到 CRM</p>
      </div>

      {/* Config Card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <ApiOutlined className="text-blue-500 text-lg" />
          <span className="font-bold text-slate-800">应用配置</span>
          <span className="text-sm text-slate-400 ml-2">企业内部应用（H5/小程序）的 AppKey 和 AppSecret</span>
        </div>

        <Form form={form} layout="vertical">
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="app_key" label="AppKey" rules={[{ required: true, message: '请输入AppKey' }]}>
              <Input placeholder="请输入企业内部应用 AppKey" />
            </Form.Item>
            <Form.Item name="app_secret" label="AppSecret" rules={[{ required: true, message: '请输入AppSecret' }]}>
              <Input.Password placeholder="请输入企业内部应用 AppSecret" />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item
              name="default_password"
              label="新用户默认密码"
              tooltip="从钉钉同步的新用户将使用此密码，建议首次登录后修改"
              rules={[{ required: true }]}
            >
              <Input.Password placeholder="Changeme@123" />
            </Form.Item>
            <Form.Item
              name="root_dept_id"
              label="根部门 ID"
              tooltip="钉钉根部门 ID，通常为 1"
            >
              <InputNumber min={1} className="w-full" placeholder="1" />
            </Form.Item>
          </div>
          <div className="border-t border-slate-100 pt-4">
            <Form.Item
              name="corp_id"
              label="CorpId（企业 ID）"
              tooltip="钉钉容器内「免登」需要；在钉钉开放平台应用信息中查看。仅用于扫码登录时可留空。"
            >
              <Input placeholder="ding××××××××（用于钉钉客户端内免登）" />
            </Form.Item>
            <div className="flex items-center gap-3">
              <LoginOutlined className="text-blue-500" />
              <span className="font-medium text-slate-700">钉钉一键登录</span>
              <Form.Item name="login_enabled" valuePropName="checked" className="mb-0">
                <Switch />
              </Form.Item>
              <span className="text-sm text-slate-400">开启后登录页显示「钉钉一键登录」，在钉钉客户端内打开则自动免登</span>
            </div>
            <div className="mt-3 bg-amber-50 border border-amber-100 rounded-lg p-3 text-sm text-amber-700 space-y-1">
              <div className="font-semibold">配置 OAuth 回调地址</div>
              <div>请在钉钉开放平台 → 应用 → 安全设置 → 登录与分享，添加以下回调地址：</div>
              <div className="font-mono bg-white rounded px-2 py-1 border border-amber-200 select-all">
                {window.location.origin}/login
              </div>
            </div>
          </div>

          {/* 消息通知 / 待办 —— 统一到本页配置（原「集成配置→钉钉」已合并至此） */}
          <div className="border-t border-slate-100 pt-4 mt-2">
            <div className="flex items-center gap-2 mb-3">
              <BellOutlined className="text-emerald-500" />
              <span className="font-medium text-slate-700">消息通知 / 待办</span>
              <span className="text-sm text-slate-400">审批等业务的工作通知与钉钉个人待办（复用上方 AppKey/AppSecret）</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Form.Item name="agent_id" label="应用 AgentId" tooltip="发工作通知/待办所需，企业内部应用的 AgentId">
                <Input placeholder="应用 AgentId" />
              </Form.Item>
              <Form.Item name="crm_base_url" label="CRM 访问地址（PC）" tooltip="待办/通知卡片的 PC 端跳转域名">
                <Input placeholder="https://192.168.0.42:8410" />
              </Form.Item>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Form.Item name="crm_h5_base_url" label="CRM 移动端地址（可选）" tooltip="移动端待办深链域名，留空则同 PC">
                <Input placeholder="https://link.fourier.net.cn" />
              </Form.Item>
              <Form.Item name="webhook_url" label="群机器人 Webhook（可选）" tooltip="额外把消息发到钉钉群，可留空">
                <Input placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx" />
              </Form.Item>
            </div>
            <Form.Item name="secret" label="群机器人加签 Secret（可选）">
              <Input.Password placeholder="群机器人加签 secret，可留空" />
            </Form.Item>
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-600">
              个人待办按<b>负责人手机号</b>匹配钉钉账号下发，请确保用户已填手机号；未配置 AgentId 时仅发群消息（若填了 Webhook）。
            </div>
          </div>

          {/* 通讯录定时同步 */}
          <div className="border-t border-slate-100 pt-4 mt-2">
            <div className="flex items-center gap-3 mb-2">
              <SyncOutlined className="text-blue-500" />
              <span className="font-medium text-slate-700">通讯录定时同步</span>
              <Form.Item name="auto_sync" valuePropName="checked" className="mb-0">
                <Switch />
              </Form.Item>
              <span className="text-sm text-slate-400">每天定时自动同步部门与用户（无需手动点击）</span>
            </div>
            <Form.Item name="sync_time" label="每日同步时间（北京时间）"
              tooltip="到达该时间后由后台任务自动执行一次部门+用户同步，格式 HH:MM">
              <Input className="!w-40" placeholder="02:00" />
            </Form.Item>
            {lastSyncAt && (
              <div className="text-[12px] text-slate-400">
                上次自动同步：{new Date(lastSyncAt).toLocaleString('zh-CN')}
              </div>
            )}
          </div>
        </Form>

        <div className="flex gap-3 mt-2">
          <Button type="primary" loading={saving} onClick={handleSave}>保存配置</Button>
          <Button loading={testing} icon={<ApiOutlined />} onClick={handleTest}>测试连接</Button>
        </div>

        {testResult && (
          <div className="mt-3">
            {testResult.connected ? (
              <Alert
                type="success"
                icon={<CheckCircleOutlined />}
                showIcon
                message={`连接成功 — 钉钉共有 ${testResult.dept_count} 个部门`}
              />
            ) : (
              <Alert
                type="error"
                icon={<CloseCircleOutlined />}
                showIcon
                message={`连接失败：${testResult.error || '未知错误'}`}
              />
            )}
          </div>
        )}
      </div>

      {/* Sync Operations */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-5">
        <div className="flex items-center gap-2 mb-1">
          <SyncOutlined className="text-emerald-500 text-lg" />
          <span className="font-bold text-slate-800">数据同步</span>
        </div>
        <p className="text-sm text-slate-400 mb-5">建议先同步部门，再同步用户（用户同步时会自动关联部门和设置主管）</p>

        {/* Sync Departments */}
        <div className="border border-slate-100 rounded-lg p-4 mb-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <ApartmentOutlined className="text-blue-500" />
                <span className="font-semibold text-slate-700">同步部门</span>
              </div>
              <p className="text-sm text-slate-400">
                从钉钉拉取全部部门，按层级结构创建或更新本地部门。同时同步部门主管（若本地已有对应用户）。
              </p>
            </div>
            <Button
              type="primary"
              ghost
              icon={syncingDepts ? <SyncOutlined spin /> : <ApartmentOutlined />}
              loading={syncingDepts}
              onClick={handleSyncDepts}
              className="shrink-0"
            >
              开始同步
            </Button>
          </div>
          {renderProgress(deptProgress)}
          {deptResult && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Tag color="green">新建 {deptResult.created} 个</Tag>
              <Tag color="blue">更新 {deptResult.updated} 个</Tag>
              <Tag color="purple">主管更新 {deptResult.leader_updated} 个</Tag>
              <Tag>共 {deptResult.total} 个</Tag>
            </div>
          )}
        </div>

        <Divider className="my-3" />

        {/* Sync Users */}
        <div className="border border-slate-100 rounded-lg p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <TeamOutlined className="text-emerald-500" />
                <span className="font-semibold text-slate-700">同步用户 & 部门主管</span>
              </div>
              <p className="text-sm text-slate-400">
                从钉钉拉取全部员工，按手机号匹配本地用户。未匹配的新员工将以默认密码创建账号，同时更新各部门主管。
              </p>
            </div>
            <Button
              type="primary"
              ghost
              icon={syncingUsers ? <SyncOutlined spin /> : <TeamOutlined />}
              loading={syncingUsers}
              onClick={handleSyncUsers}
              className="shrink-0"
            >
              开始同步
            </Button>
          </div>
          {renderProgress(userProgress)}
          {userResult && (
            <div className="mt-3 space-y-2">
              <div className="flex flex-wrap gap-2">
                <Tag color="green">新建 {userResult.created} 人</Tag>
                <Tag color="blue">更新 {userResult.updated} 人</Tag>
                <Tag color="default">无变化 {userResult.skipped} 人</Tag>
                <Tag color="purple">主管更新 {userResult.leader_updated} 个</Tag>
                {userResult.failed.length > 0 && <Tag color="red">失败 {userResult.failed.length} 人</Tag>}
                <Tag>共 {userResult.total} 人</Tag>
              </div>
              {userResult.failed.length > 0 && (
                <div className="max-h-36 overflow-y-auto bg-red-50 rounded p-2">
                  {userResult.failed.map((f, i) => (
                    <div key={i} className="text-sm text-red-600">
                      <span className="font-mono mr-2">{f.userid}</span>{f.reason}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Notes */}
      <div className="bg-blue-50 rounded-xl border border-blue-100 p-4">
        <div className="flex items-center gap-2 mb-2">
          <UserOutlined className="text-blue-500" />
          <span className="font-semibold text-blue-700 text-sm">使用说明</span>
        </div>
        <ul className="text-sm text-blue-600 space-y-1 list-disc list-inside">
          <li>需在钉钉开放平台创建「企业内部应用」，获取 AppKey 和 AppSecret</li>
          <li>应用需开通「通讯录」权限：成员管理（只读）+ 部门管理（只读）</li>
          <li>启用一键登录还需在应用「登录与分享」中添加 OAuth 回调地址（见上方提示）</li>
          <li>一键登录以<b>手机号</b>匹配本地账号，建议先同步用户再启用登录</li>
          <li>用户同步以<b>手机号</b>为主键匹配本地账号；无手机号的钉钉员工将跳过</li>
          <li>已存在的本地用户密码不会被覆盖，仅同步姓名、邮箱、手机号和部门信息</li>
          <li>新建用户默认密码在「应用配置」中设置，建议强制首次登录修改</li>
        </ul>
      </div>
    </div>
  )
}
