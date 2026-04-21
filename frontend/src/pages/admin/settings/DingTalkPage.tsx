import { useState, useEffect } from 'react'
import { Button, Form, Input, InputNumber, Switch, message, Alert, Spin, Divider, Tag } from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined,
  ApiOutlined, TeamOutlined, ApartmentOutlined, UserOutlined, LoginOutlined,
} from '@ant-design/icons'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'

interface DingTalkConfig {
  app_key: string
  app_secret: string
  default_password: string
  root_dept_id: number
  login_enabled: boolean
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

const api = {
  getConfig: () => client.get<unknown, ApiResponse<DingTalkConfig | null>>('/api/admin/v1/tenant/dingtalk/config'),
  saveConfig: (data: Partial<DingTalkConfig>) =>
    client.post<unknown, ApiResponse<{ saved: boolean }>>('/api/admin/v1/tenant/dingtalk/config', data),
  testConnection: () =>
    client.post<unknown, ApiResponse<{ connected: boolean; dept_count?: number; error?: string }>>('/api/admin/v1/tenant/dingtalk/test'),
  syncDepts: (syncLeaders = true) =>
    client.post<unknown, ApiResponse<SyncDeptResult>>(`/api/admin/v1/tenant/dingtalk/sync/departments?sync_leaders=${syncLeaders}`),
  syncUsers: () =>
    client.post<unknown, ApiResponse<SyncUserResult>>('/api/admin/v1/tenant/dingtalk/sync/users'),
}

export default function DingTalkPage() {
  usePageTitle('钉钉集成')
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [syncingDepts, setSyncingDepts] = useState(false)
  const [syncingUsers, setSyncingUsers] = useState(false)

  const [testResult, setTestResult] = useState<{ connected: boolean; dept_count?: number; error?: string } | null>(null)
  const [deptResult, setDeptResult] = useState<SyncDeptResult | null>(null)
  const [userResult, setUserResult] = useState<SyncUserResult | null>(null)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    setLoading(true)
    try {
      const res = await api.getConfig()
      if (res.data) {
        form.setFieldsValue({
          app_key: res.data.app_key,
          app_secret: res.data.app_secret,
          default_password: res.data.default_password || 'Changeme@123',
          root_dept_id: res.data.root_dept_id || 1,
          login_enabled: res.data.login_enabled || false,
        })
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
    try {
      const res = await api.syncDepts(true)
      setDeptResult(res.data)
      message.success(`部门同步完成：新建 ${res.data.created}，更新 ${res.data.updated}`)
    } catch (e: any) {
      message.error(e?.response?.data?.message || '同步部门失败')
    } finally {
      setSyncingDepts(false)
    }
  }

  const handleSyncUsers = async () => {
    setSyncingUsers(true)
    setUserResult(null)
    try {
      const res = await api.syncUsers()
      setUserResult(res.data)
      const { created, updated, failed } = res.data
      if (failed.length === 0) {
        message.success(`用户同步完成：新建 ${created}，更新 ${updated}`)
      } else {
        message.warning(`用户同步完成：新建 ${created}，更新 ${updated}，失败 ${failed.length}`)
      }
    } catch (e: any) {
      message.error(e?.response?.data?.message || '同步用户失败')
    } finally {
      setSyncingUsers(false)
    }
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
            <div className="flex items-center gap-3">
              <LoginOutlined className="text-blue-500" />
              <span className="font-medium text-slate-700">钉钉一键登录</span>
              <Form.Item name="login_enabled" valuePropName="checked" className="mb-0">
                <Switch />
              </Form.Item>
              <span className="text-sm text-slate-400">开启后登录页将显示「钉钉一键登录」按钮</span>
            </div>
            <div className="mt-3 bg-amber-50 border border-amber-100 rounded-lg p-3 text-sm text-amber-700 space-y-1">
              <div className="font-semibold">配置 OAuth 回调地址</div>
              <div>请在钉钉开放平台 → 应用 → 安全设置 → 登录与分享，添加以下回调地址：</div>
              <div className="font-mono bg-white rounded px-2 py-1 border border-amber-200 select-all">
                {window.location.origin}/login
              </div>
            </div>
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
