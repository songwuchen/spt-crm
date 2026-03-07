import { useState, useRef } from 'react'
import { Modal, Upload, Button, Table, Tag, Alert, message, Steps } from 'antd'
import { UploadOutlined, InboxOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload'

interface ImportModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  previewUrl: string
  importUrl: string
  title?: string
  expectedHeaders?: string[]
}

interface PreviewData {
  headers: string[]
  rows: string[][]
  duplicates: number[]
}

export default function ImportModal({
  open, onClose, onSuccess,
  previewUrl, importUrl,
  title = '导入数据',
  expectedHeaders,
}: ImportModalProps) {
  const [step, setStep] = useState(0)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<PreviewData | null>(null)
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<{ created: number; skipped: number; errors: string[] } | null>(null)

  const reset = () => {
    setStep(0)
    setFile(null)
    setPreview(null)
    setResult(null)
    setLoading(false)
    setImporting(false)
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

  const columns = preview?.headers.map((h, i) => ({
    title: h,
    dataIndex: String(i),
    key: String(i),
    width: 120,
    ellipsis: true,
    render: (v: string) => v || <span className="text-slate-300">-</span>,
  })) || []

  const dataSource = preview?.rows.map((row, idx) => {
    const record: Record<string, any> = { _key: idx, _dup: dupSet.has(idx) }
    row.forEach((cell, ci) => { record[String(ci)] = cell })
    return record
  }) || []

  return (
    <Modal
      title={title}
      open={open}
      onCancel={handleClose}
      width={900}
      footer={null}
      destroyOnClose
    >
      <Steps current={step} size="small" className="mb-6"
        items={[
          { title: '上传文件' },
          { title: '预览确认' },
          { title: '导入结果' },
        ]}
      />

      {step === 0 && (
        <div>
          {expectedHeaders && (
            <Alert type="info" showIcon className="mb-4"
              message={`文件格式要求：第一行为表头，列顺序为：${expectedHeaders.join('、')}`}
            />
          )}
          <Upload.Dragger
            accept=".xlsx,.xls"
            showUploadList={false}
            beforeUpload={(f) => { handlePreview(f); return false }}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽Excel文件到此处</p>
            <p className="ant-upload-hint">支持 .xlsx / .xls 格式</p>
          </Upload.Dragger>
          {loading && <div className="text-center mt-4 text-slate-500">解析中...</div>}
        </div>
      )}

      {step === 1 && preview && (
        <div>
          <div className="flex items-center gap-4 mb-3">
            <span className="text-sm text-slate-600">共 <b>{preview.rows.length}</b> 条数据</span>
            {dupSet.size > 0 && (
              <Tag color="warning">{dupSet.size} 条重复（已存在同名客户，导入时将自动跳过）</Tag>
            )}
          </div>
          <Table
            size="small"
            columns={columns}
            dataSource={dataSource}
            rowKey="_key"
            scroll={{ x: columns.length * 120, y: 360 }}
            pagination={false}
            rowClassName={(record) => record._dup ? 'bg-amber-50' : ''}
          />
          <div className="flex justify-end gap-2 mt-4">
            <Button onClick={() => { setStep(0); setPreview(null); setFile(null) }}>重新选择</Button>
            <Button type="primary" loading={importing} onClick={handleImport}>
              确认导入 ({preview.rows.length - dupSet.size} 条)
            </Button>
          </div>
        </div>
      )}

      {step === 2 && result && (
        <div className="text-center py-6">
          <div className="text-5xl mb-4">✅</div>
          <div className="text-lg font-bold text-slate-900 mb-2">导入完成</div>
          <div className="flex justify-center gap-6 mb-4">
            <div>
              <div className="text-2xl font-black text-emerald-600">{result.created}</div>
              <div className="text-xs text-slate-500">成功导入</div>
            </div>
            {result.skipped > 0 && (
              <div>
                <div className="text-2xl font-black text-amber-600">{result.skipped}</div>
                <div className="text-xs text-slate-500">重复跳过</div>
              </div>
            )}
            {result.errors.length > 0 && (
              <div>
                <div className="text-2xl font-black text-red-600">{result.errors.length}</div>
                <div className="text-xs text-slate-500">导入失败</div>
              </div>
            )}
          </div>
          {result.errors.length > 0 && (
            <div className="text-left bg-red-50 rounded-lg p-3 max-h-40 overflow-auto text-xs text-red-700">
              {result.errors.map((e, i) => <div key={i}>{e}</div>)}
            </div>
          )}
          <Button type="primary" className="mt-4" onClick={handleClose}>完成</Button>
        </div>
      )}
    </Modal>
  )
}
