import { useEffect, useState } from 'react'
import { Select, Input, Switch, Button, Space, Alert, message, Divider } from 'antd'
import { settingsApi } from '@/api/settings'

type StorageType = 'local' | 'minio' | 'oss'

interface ProviderConfig {
  endpoint?: string
  access_key?: string
  secret_key?: string
  bucket?: string
  region?: string
  secure?: boolean
  public_base_url?: string
  key_prefix?: string
}

interface ImmConfig {
  enabled?: boolean
  project?: string
  region?: string
  endpoint?: string
  from_env?: boolean
}

const STORAGE_OPTIONS = [
  { value: 'local', label: '本地磁盘（默认）' },
  { value: 'minio', label: 'MinIO / S3 兼容' },
  { value: 'oss', label: '阿里云 OSS（CRM 新上传）' },
]

const SECRET_PLACEHOLDER = '已配置，如需修改请重新输入'

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <label className="text-sm font-medium text-slate-700 mb-1 block">{label}</label>
      {children}
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
    </div>
  )
}

export default function FileStorageTab() {
  const [storageType, setStorageType] = useState<StorageType>('local')
  const [minio, setMinio] = useState<ProviderConfig>({})
  const [oss, setOss] = useState<ProviderConfig>({})
  const [jdyOss, setJdyOss] = useState<ProviderConfig>({})
  const [imm, setImm] = useState<ImmConfig>({ enabled: false })
  const [minioHasSecret, setMinioHasSecret] = useState(false)
  const [ossHasSecret, setOssHasSecret] = useState(false)
  const [jdyOssHasSecret, setJdyOssHasSecret] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testingJdy, setTestingJdy] = useState(false)
  const [dirty, setDirty] = useState(false)

  const load = () => {
    settingsApi.getFileStorage().then((r: {
      data: {
        storage_type: StorageType
        minio?: ProviderConfig
        oss?: ProviderConfig
        jdy_oss?: ProviderConfig
        imm?: ImmConfig
      }
    }) => {
      const d = r.data
      if (!d) return
      setStorageType(d.storage_type || 'local')
      const m = d.minio || {}
      const o = d.oss || {}
      const j = d.jdy_oss || {}
      setMinioHasSecret(m.secret_key === '***')
      setOssHasSecret(o.secret_key === '***')
      setJdyOssHasSecret(j.secret_key === '***')
      setMinio({ ...m, secret_key: '' })
      setOss({ ...o, secret_key: '' })
      setJdyOss({ ...j, secret_key: '' })
      setImm({
        enabled: !!d.imm?.enabled || (!!d.imm?.project && !d.imm?.from_env),
        project: d.imm?.project || '',
        region: d.imm?.region || '',
        endpoint: d.imm?.endpoint || '',
        from_env: !!d.imm?.from_env,
      })
      if (d.imm?.from_env && d.imm?.project) {
        setImm((prev) => ({ ...prev, enabled: true, from_env: true }))
      }
      setDirty(false)
    }).catch(() => {})
  }

  useEffect(() => { load() }, [])

  const buildPayload = () => {
    const payload: Record<string, unknown> = { storage_type: storageType }
    payload.minio = { ...minio }
    payload.oss = { ...oss }
    payload.jdy_oss = { ...jdyOss }
    if (!minio.secret_key) delete (payload.minio as ProviderConfig).secret_key
    if (!oss.secret_key) delete (payload.oss as ProviderConfig).secret_key
    if (!jdyOss.secret_key) delete (payload.jdy_oss as ProviderConfig).secret_key
    payload.imm = {
      enabled: !!imm.enabled,
      project: (imm.project || '').trim(),
      region: (imm.region || '').trim(),
      endpoint: (imm.endpoint || '').trim(),
    }
    return payload
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await settingsApi.updateFileStorage(buildPayload())
      message.success('文件存储配置已保存')
      load()
    } catch { message.error('保存失败') }
    finally { setSaving(false) }
  }

  const handleTest = async (type: StorageType | 'jdy_oss') => {
    if (dirty) { message.info('请先保存配置再测试连接'); return }
    const setLoading = type === 'jdy_oss' ? setTestingJdy : setTesting
    setLoading(true)
    try {
      const res = await settingsApi.testFileStorage(type) as { data: { connected: boolean; error?: string } }
      if (res.data?.connected) message.success('连接成功')
      else message.warning(`连接失败：${res.data?.error || '无法连接'}`)
    } catch { message.error('测试连接失败') }
    finally { setLoading(false) }
  }

  const updateMinio = (patch: Partial<ProviderConfig>) => { setMinio({ ...minio, ...patch }); setDirty(true) }
  const updateOss = (patch: Partial<ProviderConfig>) => { setOss({ ...oss, ...patch }); setDirty(true) }
  const updateJdyOss = (patch: Partial<ProviderConfig>) => { setJdyOss({ ...jdyOss, ...patch }); setDirty(true) }
  const updateImm = (patch: Partial<ImmConfig>) => {
    setImm({ ...imm, ...patch, from_env: false })
    setDirty(true)
  }

  return (
    <div className="pb-6 max-w-xl">
      <p className="text-sm text-slate-500 mb-4">
        上方选择 CRM 新附件的默认上传后端；下方单独配置简道云迁移历史附件所在的 OSS 桶（只读阅览/下载）。
        切换默认后端后，已上传文件仍从原后端读取。密钥 AES 加密存储，保存后不再明文返回。
      </p>

      <div className="space-y-4">
        <Field label="CRM 默认存储后端">
          <Select<StorageType> value={storageType} style={{ width: 280 }}
            onChange={(v) => { setStorageType(v); setDirty(true) }}
            options={STORAGE_OPTIONS} />
        </Field>

        {storageType === 'local' && (
          <Alert type="info" showIcon message="使用服务器本地磁盘存储（UPLOAD_DIR），无需额外配置。" />
        )}

        {storageType === 'minio' && (
          <div className="space-y-3 p-4 bg-slate-50 rounded-lg border border-slate-100">
            <Field label="Endpoint" hint="主机:端口，不含 http(s)://，例如 192.168.0.42:9000">
              <Input value={minio.endpoint || ''} placeholder="192.168.0.42:9000"
                onChange={(e) => updateMinio({ endpoint: e.target.value })} />
            </Field>
            <Field label="Bucket">
              <Input value={minio.bucket || ''} placeholder="crm-files"
                onChange={(e) => updateMinio({ bucket: e.target.value })} />
            </Field>
            <Field label="Access Key">
              <Input value={minio.access_key || ''} autoComplete="off"
                onChange={(e) => updateMinio({ access_key: e.target.value })} />
            </Field>
            <Field label="Secret Key">
              <Input.Password value={minio.secret_key || ''} autoComplete="new-password"
                placeholder={minioHasSecret ? SECRET_PLACEHOLDER : ''}
                onChange={(e) => updateMinio({ secret_key: e.target.value })} />
            </Field>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700">启用 HTTPS</span>
              <Switch checked={!!minio.secure} onChange={(v) => updateMinio({ secure: v })} />
            </div>
            <Field label="Region（可选）">
              <Input value={minio.region || ''} onChange={(e) => updateMinio({ region: e.target.value })} />
            </Field>
          </div>
        )}

        {storageType === 'oss' && (
          <div className="space-y-3 p-4 bg-slate-50 rounded-lg border border-slate-100">
            <Field label="Endpoint" hint="例如 https://oss-cn-hangzhou.aliyuncs.com">
              <Input value={oss.endpoint || ''} placeholder="https://oss-cn-hangzhou.aliyuncs.com"
                onChange={(e) => updateOss({ endpoint: e.target.value })} />
            </Field>
            <Field label="Bucket">
              <Input value={oss.bucket || ''} placeholder="crm-files"
                onChange={(e) => updateOss({ bucket: e.target.value })} />
            </Field>
            <Field label="AccessKey ID">
              <Input value={oss.access_key || ''} autoComplete="off"
                onChange={(e) => updateOss({ access_key: e.target.value })} />
            </Field>
            <Field label="AccessKey Secret">
              <Input.Password value={oss.secret_key || ''} autoComplete="new-password"
                placeholder={ossHasSecret ? SECRET_PLACEHOLDER : ''}
                onChange={(e) => updateOss({ secret_key: e.target.value })} />
            </Field>
          </div>
        )}

        <Divider orientation="left" plain className="!my-2">
          <span className="text-slate-500 text-sm">简道云历史 OSS（只读）</span>
        </Divider>

        <Alert
          type="info"
          showIcon
          className="!mb-0"
          message="专用于从简道云迁移过来的历史附件阅览/下载"
          description="与上方 CRM 默认 OSS 相互独立：新上传仍走 CRM 桶；表单里带 ossKey 的迁移附件走此桶预签名链接。"
        />

        <div className="space-y-3 p-4 bg-amber-50/60 rounded-lg border border-amber-100">
          <Field label="Endpoint" hint="简道云附件归档桶所在地域 Endpoint">
            <Input value={jdyOss.endpoint || ''} placeholder="https://oss-cn-hangzhou.aliyuncs.com"
              onChange={(e) => updateJdyOss({ endpoint: e.target.value })} />
          </Field>
          <Field label="Bucket">
            <Input value={jdyOss.bucket || ''} placeholder="jdy-archive"
              onChange={(e) => updateJdyOss({ bucket: e.target.value })} />
          </Field>
          <Field label="AccessKey ID">
            <Input value={jdyOss.access_key || ''} autoComplete="off"
              onChange={(e) => updateJdyOss({ access_key: e.target.value })} />
          </Field>
          <Field label="AccessKey Secret">
            <Input.Password value={jdyOss.secret_key || ''} autoComplete="new-password"
              placeholder={jdyOssHasSecret ? SECRET_PLACEHOLDER : ''}
              onChange={(e) => updateJdyOss({ secret_key: e.target.value })} />
          </Field>
          <Field label="对象 Key 前缀（可选）" hint="与数据中台归档一致时一般为 datahub，仅作备注">
            <Input value={jdyOss.key_prefix || ''} placeholder="datahub"
              onChange={(e) => updateJdyOss({ key_prefix: e.target.value })} />
          </Field>
          <Button loading={testingJdy} onClick={() => void handleTest('jdy_oss')}>测试简道云 OSS 连接</Button>
        </div>

        <Divider orientation="left" plain className="!my-2">
          <span className="text-slate-500 text-sm">在线文档预览（IMM）</span>
        </Divider>

        <Alert
          type="info"
          showIcon
          className="!mb-0"
          message="用于旧版 .doc / PPT 等页内阅览（对齐简道云 / spt-lowcode）"
          description="须使用阿里云 OSS，且 IMM 项目与 Bucket 同地域。docx / PDF 仍走本地预览，不消耗 IMM。"
        />

        {storageType !== 'oss' && (
          <Alert type="warning" showIcon message="CRM 默认存储不是阿里云 OSS 时，新上传文件的 IMM 预览可能不可用；简道云历史附件仍可在配置 JDY OSS 后预览。" />
        )}

        <div className="space-y-3 p-4 bg-slate-50 rounded-lg border border-slate-100">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">启用 IMM WebOffice 预览</span>
            <Switch checked={!!imm.enabled} onChange={(v) => updateImm({ enabled: v })} />
          </div>
          {imm.from_env && (
            <p className="text-xs text-amber-600 m-0">当前值来自服务器环境变量；保存后将写入租户配置并优先生效。</p>
          )}
          <Field label="IMM 项目名称" hint="阿里云控制台 → 智能媒体管理 IMM → 项目名称">
            <Input
              value={imm.project || ''}
              disabled={!imm.enabled}
              placeholder="例如 spt-crm-imm"
              onChange={(e) => updateImm({ project: e.target.value })}
            />
          </Field>
          <Field label="Region（可选）" hint="留空则从 OSS Endpoint 推导，如 cn-hangzhou">
            <Input
              value={imm.region || ''}
              disabled={!imm.enabled}
              placeholder="cn-hangzhou"
              onChange={(e) => updateImm({ region: e.target.value })}
            />
          </Field>
          <Field label="IMM Endpoint（可选）" hint="一般留空；同地域 ECS 可用 imm-vpc.{region}.aliyuncs.com">
            <Input
              value={imm.endpoint || ''}
              disabled={!imm.enabled}
              placeholder="imm.cn-hangzhou.aliyuncs.com"
              onChange={(e) => updateImm({ endpoint: e.target.value })}
            />
          </Field>
        </div>

        <Space>
          <Button type="primary" loading={saving} onClick={handleSave}>保存配置</Button>
          {storageType !== 'local' && (
            <Button loading={testing} onClick={() => void handleTest(storageType)}>测试 CRM 存储连接</Button>
          )}
        </Space>
      </div>
    </div>
  )
}
