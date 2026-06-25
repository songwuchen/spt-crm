import { useState } from 'react'
import { Modal, Upload, Button, Table, Tag, Alert, message, Steps, Select, Tooltip } from 'antd'
import { InboxOutlined, DownloadOutlined } from '@ant-design/icons'

interface ImportModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  previewUrl: string
  importUrl: string
  templateUrl?: string
  title?: string
  expectedHeaders?: string[]
}

interface PreviewData {
  headers: string[]
  rows: string[][]
  duplicates: number[]
  errors?: Record<number, string>
}

export default function ImportModal({
  open, onClose, onSuccess,
  previewUrl, importUrl, templateUrl,
  title = '导入数据',
  expectedHeaders,
}: ImportModalProps) {
  const [step, setStep] = useState(0)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<PreviewData | null>(null)
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<{ created: number; skipped: number; errors: string[] } | null>(null)
  const [fieldMapping, setFieldMapping] = useState<Record<number, number>>({})
  const [skipErrors, setSkipErrors] = useState(true)

  const reset = () => {
    setStep(0)
    setFile(null)
    setPreview(null)
    setResult(null)
    setLoading(false)
    setImporting(false)
    setFieldMapping({})
    setSkipErrors(true)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const handlePreview = async (f: File) => {
    setFile(f)
    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', f)
      const token = localStorage.getItem('access_token')
      const res = await fetch(previewUrl, {
        method: 'POST', body: formData,
        headers: { Authorization: `Bearer ${token}` },
      })
      const json = await res.json()
      if (json.code === 0) {
        setPreview(json.data)
        // Auto-map columns by matching header names
        if (expectedHeaders && json.data.headers) {
          const mapping: Record<number, number> = {}
          expectedHeaders.forEach((eh, ei) => {
            const matchIdx = json.data.headers.findIndex(
              (h: string) => h.trim().toLowerCase() === eh.trim().toLowerCase()
            )
            if (matchIdx >= 0) mapping[ei] = matchIdx
          })
          setFieldMapping(mapping)
        }
        setStep(1)
      } else {
        message.error(json.message || '解析失败')
      }
    } catch {
      message.error('文件解析失败')
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async () => {
    if (!file) return
    setImporting(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      if (Object.keys(fieldMapping).length > 0) {
        formData.append('field_mapping', JSON.stringify(fieldMapping))
      }
      formData.append('skip_errors', String(skipErrors))
      const token = localStorage.getItem('access_token')
      const res = await fetch(importUrl, {
        method: 'POST', body: formData,
        headers: { Authorization: `Bearer ${token}` },
      })
      const json = await res.json()
      if (json.code === 0) {
        setResult(json.data)
        setStep(2)
        onSuccess()
      } else {
        message.error(json.message || '导入失败')
      }
    } catch {
      message.error('导入失败')
    } finally {
      setImporting(false)
    }
  }

  const dupSet = new Set(preview?.duplicates || [])
  const errMap = preview?.errors || {}
  const errSet = new Set(Object.keys(errMap).map(Number))

  // Leading status column: shows the per-row error reason (or 重复/可导入) so users
  // can see *why* a row failed instead of just a red highlight.
  const statusColumn = (errSet.size > 0 || dupSet.size > 0)
    ? [{
        title: '状态',
        key: '_status',
        fixed: 'left' as const,
        width: 220,
        render: (_: unknown, record: any) => {
          if (record._err) return <span className="text-red-500 text-xs">{record._errMsg || '校验失败'}</span>
          if (record._dup) return <Tag color="warning">重复</Tag>
          return <Tag color="success">可导入</Tag>
        },
      }]
    : []

  const columns = [...statusColumn, ...(preview?.headers.map((h, i) => ({
    title: () => (
      <div className="space-y-1">
        <div className="text-sm font-bold truncate">{h}</div>
        {expectedHeaders && (
          <Select size="small" className="w-full" allowClear
            placeholder="映射到..."
            value={Object.entries(fieldMapping).find(([, v]) => v === i)?.[0] != null
              ? Number(Object.entries(fieldMapping).find(([, v]) => v === i)![0])
              : undefined}
            onChange={(targetIdx) => {
              const next = { ...fieldMapping }
              // Remove existing mapping to this column
              Object.entries(next).forEach(([k, v]) => { if (v === i) delete next[Number(k)] })
              if (targetIdx != null) next[targetIdx] = i
              setFieldMapping(next)
            }}
            options={expectedHeaders.map((eh, ei) => ({ label: eh, value: ei }))}
          />
        )}
      </div>
    ),
    dataIndex: String(i),
    key: String(i),
    width: expectedHeaders ? 150 : 120,
    ellipsis: true,
    render: (v: string, record: any) => {
      const hasErr = record._err
      return (
        <span className={hasErr ? 'text-red-500' : ''}>{v || <span className="text-slate-300">-</span>}</span>
      )
    },
  })) || [])]

  const dataSource = preview?.rows.map((row, idx) => {
    const record: Record<string, any> = { _key: idx, _dup: dupSet.has(idx), _err: errSet.has(idx), _errMsg: errMap[idx] }
    row.forEach((cell, ci) => { record[String(ci)] = cell })
    return record
  }) || []

  const errorCount = errSet.size
  const validCount = (preview?.rows.length || 0) - dupSet.size - errorCount

  return (
    <Modal
      title={title}
      open={open}
      onCancel={handleClose}
      width={960}
      footer={null}
      destroyOnClose
    >
      <Steps current={step} size="small" className="mb-6"
        items={[
          { title: '上传文件' },
          { title: '字段映射 + 预览' },
          { title: '导入结果' },
        ]}
      />

      {step === 0 && (
        <div>
          {expectedHeaders && (
            <Alert type="info" showIcon className="mb-4"
              message={
                <div className="flex items-center justify-between">
                  <span>文件格式要求：第一行为表头，期望列：{expectedHeaders.join('、')}</span>
                  {templateUrl && (
                    <Button size="small" icon={<DownloadOutlined />} type="link"
                      onClick={() => {
                        const token = localStorage.getItem('access_token')
                        const a = document.createElement('a')
                        fetch(templateUrl, { headers: { Authorization: `Bearer ${token}` } })
                          .then(r => r.blob())
                          .then(blob => {
                            a.href = URL.createObjectURL(blob)
                            a.download = 'import_template.xlsx'
                            a.click()
                            URL.revokeObjectURL(a.href)
                          })
                      }}
                    >下载模板</Button>
                  )}
                </div>
              }
            />
          )}
          <Upload.Dragger
            accept=".xlsx,.xls,.csv"
            showUploadList={false}
            beforeUpload={(f) => { handlePreview(f); return false }}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽文件到此处</p>
            <p className="ant-upload-hint">支持 .xlsx / .xls / .csv 格式</p>
          </Upload.Dragger>
          {loading && <div className="text-center mt-4 text-slate-500">解析中...</div>}
        </div>
      )}

      {step === 1 && preview && (
        <div>
          <div className="flex items-center gap-4 mb-3 flex-wrap">
            <span className="text-sm text-slate-600">共 <b>{preview.rows.length}</b> 条数据</span>
            {dupSet.size > 0 && (
              <Tag color="warning">{dupSet.size} 条重复</Tag>
            )}
            {errorCount > 0 && (
              <Tag color="error">{errorCount} 条有错误</Tag>
            )}
            <Tag color="success">{validCount} 条可导入</Tag>
            {errorCount > 0 && (
              <label className="flex items-center gap-1.5 text-sm text-slate-600 ml-auto">
                <input type="checkbox" checked={skipErrors} onChange={(e) => setSkipErrors(e.target.checked)}
                  className="accent-primary" />
                跳过错误行继续导入
              </label>
            )}
          </div>
          <Table
            size="small"
            columns={columns}
            dataSource={dataSource}
            rowKey="_key"
            scroll={{ x: columns.length * (expectedHeaders ? 150 : 120), y: 320 }}
            pagination={false}
            rowClassName={(record) => {
              if (record._err) return 'bg-red-50'
              if (record._dup) return 'bg-amber-50'
              return ''
            }}
          />
          <div className="flex justify-end gap-2 mt-4">
            <Button onClick={() => { setStep(0); setPreview(null); setFile(null); setFieldMapping({}) }}>重新选择</Button>
            <Button type="primary" loading={importing} onClick={handleImport}
              disabled={validCount <= 0}>
              确认导入 ({validCount} 条)
            </Button>
          </div>
        </div>
      )}

      {step === 2 && result && (
        <div className="text-center py-6">
          <div className="text-5xl mb-4">{result.errors.length > 0 && result.created === 0 ? '❌' : '✅'}</div>
          <div className="text-lg font-bold text-slate-900 mb-2">导入完成</div>
          <div className="flex justify-center gap-6 mb-4">
            <div>
              <div className="text-2xl font-black text-emerald-600">{result.created}</div>
              <div className="text-sm text-slate-500">成功导入</div>
            </div>
            {result.skipped > 0 && (
              <div>
                <div className="text-2xl font-black text-amber-600">{result.skipped}</div>
                <div className="text-sm text-slate-500">重复跳过</div>
              </div>
            )}
            {result.errors.length > 0 && (
              <div>
                <div className="text-2xl font-black text-red-600">{result.errors.length}</div>
                <div className="text-sm text-slate-500">导入失败</div>
              </div>
            )}
          </div>
          {result.errors.length > 0 && (
            <div className="text-left bg-red-50 rounded-lg p-3 max-h-40 overflow-auto text-sm text-red-700">
              {result.errors.map((e, i) => <div key={i}>{e}</div>)}
            </div>
          )}
          <Button type="primary" className="mt-4" onClick={handleClose}>完成</Button>
        </div>
      )}
    </Modal>
  )
}
