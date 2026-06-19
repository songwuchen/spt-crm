import { useEffect, useState } from 'react'
import { Select, Input, Switch, Button, Space, Alert, message } from 'antd'
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
}

const STORAGE_OPTIONS = [
  { value: 'local', label: '本地磁盘（默认）' },
  { value: 'minio', label: 'MinIO / S3 兼容' },
  { value: 'oss', label: '阿里云 OSS' },
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
  // Whether a secret is already stored on the server (masked as ***)
  const [minioHasSecret, setMinioHasSecret] = useState(false)
  const [ossHasSecret, setOssHasSecret] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [dirty, setDirty] = useState(false)

  const load = () => {
    settingsApi.getFileStorage().then((r: { data: { storage_type: StorageType; minio?: ProviderConfig; oss?: ProviderConfig } }) => {
      const d = r.data
      if (!d) return
      setStorageType(d.storage_type || 'local')
      const m = d.minio || {}
      const o = d.oss || {}
      setMinioHasSecret(m.secret_key === '***')
      setOssHasSecret(o.secret_key === '***')
      // Don't keep the masked secret in the editable field
      setMinio({ ...m, secret_key: '' })
      setOss({ ...o, secret_key: '' })
      setDirty(false)
    }).catch(() => {})
  }

  useEffect(() => { load() }, [])

  const buildPayload = () => {
    const payload: Record<string, unknown> = { storage_type: storageType }
    // Only send a provider block if it carries data, so we never clobber stored secrets
    payload.minio = { ...minio }
    payload.oss = { ...oss }
    // Drop empty secret so the backend keeps the stored one
    if (!minio.secret_key) delete (payload.minio as ProviderConfig).secret_key
    if (!oss.secret_key) delete (payload.oss as ProviderConfig).secret_key
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

  const handleTest = async () => {
    if (dirty) { message.info('请先保存配置再测试连接'); return }
    setTesting(true)
    try {
      const res = await settingsApi.testFileStorage(storageType) as { data: { connected: boolean; error?: string } }
      if (res.data?.connected) message.success('连接成功')
      else message.warning(`连接失败：${res.data?.error || '无法连接'}`)
    } catch { message.error('测试连接失败') }
    finally { setTesting(false) }
  }

  const updateMinio = (patch: Partial<ProviderConfig>) => { setMinio({ ...minio, ...patch }); setDirty(true) }
  const updateOss = (patch: Partial<ProviderConfig>) => { setOss({ ...oss, ...patch }); setDirty(true) }

  return (
    <div className="pb-6 max-w-xl">
      <p className="text-sm text-slate-500 mb-4">
        选择附件、合同等文件的存储后端。切换后端后，已上传的历史文件仍会从其原始后端读取，不会丢失。
        密钥使用 AES 加密存储，保存后不会再明文返回。
      </p>

      <div className="space-y-4">
        <Field label="存储后端">
          <Select<StorageType> value={storageType} style={{ width: 240 }}
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

        <Space>
          <Button type="primary" loading={saving} onClick={handleSave}>保存配置</Button>
          {storageType !== 'local' && (
            <Button loading={testing} onClick={handleTest}>测试连接</Button>
          )}
        </Space>
      </div>
    </div>
  )
}
