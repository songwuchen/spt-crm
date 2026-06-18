import { useState } from 'react'
import { Modal, Button, message, Upload } from 'antd'
import { UploadOutlined, FileExcelOutlined, DownloadOutlined } from '@ant-design/icons'
import client from '@/api/client'

interface ImportExcelModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  apiUrl: string
  title?: string
  templateColumns: string[]
  templateUrl?: string
}

export default function ImportExcelModal({ open, onClose, onSuccess, apiUrl, title = '导入Excel', templateColumns, templateUrl }: ImportExcelModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ created: number; skipped: number; errors: string[] } | null>(null)

  const handleUpload = async () => {
    if (!file) { message.warning('请选择文件'); return }
    setLoading(true)
    setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await client.post(apiUrl, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }) as any
      const data = res.data || res
      setResult(data)
      if (data.created > 0) {
        message.success(`成功导入 ${data.created} 条`)
        onSuccess()
      } else if (data.skipped > 0) {
        message.info(`全部跳过（${data.skipped} 条重复）`)
      }
    } catch {
      message.error('导入失败')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setFile(null)
    setResult(null)
    onClose()
  }

  const downloadTemplate = async () => {
    if (!templateUrl) return
    try {
      const res = await client.get(templateUrl, { responseType: 'blob' }) as unknown as Blob
      const url = URL.createObjectURL(res)
      const a = document.createElement('a')
      a.href = url; a.download = 'import_template.xlsx'; a.click()
      URL.revokeObjectURL(url)
    } catch { message.error('模板下载失败') }
  }

  return (
    <Modal title={title} open={open} onCancel={handleClose}
      footer={[
        <Button key="cancel" onClick={handleClose}>关闭</Button>,
        <Button key="upload" type="primary" onClick={handleUpload} loading={loading}
          disabled={!file} icon={<UploadOutlined />}>
          开始导入
        </Button>,
      ]} width={520}>
      <div className="space-y-4">
        <div className="p-3 bg-blue-50 rounded-lg border border-blue-100 text-sm text-blue-800">
          <p className="font-bold mb-1">Excel 格式要求：</p>
          <p>第一行为表头，从第二行开始为数据。列顺序：</p>
          <div className="flex flex-wrap gap-1 mt-1">
            {templateColumns.map((col, i) => (
              <span key={i} className="px-1.5 py-0.5 bg-blue-100 rounded text-sm font-mono">{col}</span>
            ))}
          </div>
          {templateUrl && (
            <Button type="link" size="small" className="px-0 mt-1" icon={<DownloadOutlined />} onClick={downloadTemplate}>
              下载导入模板
            </Button>
          )}
        </div>

        <Upload.Dragger
          accept=".xlsx,.csv"
          maxCount={1}
          beforeUpload={(f) => { setFile(f); setResult(null); return false }}
          onRemove={() => { setFile(null); setResult(null) }}
          fileList={file ? [{ uid: '-1', name: file.name, status: 'done' } as any] : []}
        >
          <p className="ant-upload-drag-icon"><FileExcelOutlined style={{ fontSize: 32, color: '#10b981' }} /></p>
          <p className="ant-upload-text text-sm">点击或拖拽文件到此区域</p>
          <p className="ant-upload-hint text-sm text-slate-400">支持 .xlsx / .csv（旧版 .xls 请先另存为 .xlsx）</p>
        </Upload.Dragger>

        {result && (
          <div className="p-3 rounded-lg border bg-slate-50 border-slate-200">
            <div className="flex gap-4 text-sm mb-2">
              <span className="text-emerald-600 font-bold">成功: {result.created}</span>
              <span className="text-amber-600 font-bold">跳过: {result.skipped}</span>
              {result.errors.length > 0 && (
                <span className="text-red-600 font-bold">错误: {result.errors.length}</span>
              )}
            </div>
            {result.errors.length > 0 && (
              <div className="max-h-32 overflow-y-auto text-sm text-red-600 space-y-0.5">
                {result.errors.map((e, i) => <div key={i}>{e}</div>)}
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
