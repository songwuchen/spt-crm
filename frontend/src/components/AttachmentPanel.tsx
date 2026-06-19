import { useState, useEffect } from 'react'
import { Upload, Button, Table, Modal, message } from 'antd'
import { UploadOutlined, DownloadOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons'
import { attachmentApi } from '@/api/attachment'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

interface AttachmentItem {
  id: string
  original_name: string
  content_type?: string
  file_size: number
  uploader_name?: string
  created_at: string
}

interface Props {
  bizType: string
  bizId: string
}

function isPreviewable(contentType?: string, name?: string): 'image' | 'pdf' | false {
  if (!contentType && !name) return false
  const ct = (contentType || '').toLowerCase()
  const ext = (name || '').split('.').pop()?.toLowerCase()
  if (ct.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'].includes(ext || '')) return 'image'
  if (ct === 'application/pdf' || ext === 'pdf') return 'pdf'
  return false
}

export default function AttachmentPanel({ bizType, bizId }: Props) {
  const [list, setList] = useState<AttachmentItem[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [previewItem, setPreviewItem] = useState<AttachmentItem | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string>('')

  const fetchList = async () => {
    setLoading(true)
    try {
      const res = await client.get<unknown, ApiResponse<AttachmentItem[]>>('/api/v1/attachments/by_biz', {
        params: { biz_type: bizType, biz_id: bizId },
      })
      setList(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchList() }, [bizType, bizId])

  // Resolve a usable (presigned / token-bearing) URL whenever the preview target changes.
  useEffect(() => {
    let cancelled = false
    if (!previewItem) { setPreviewUrl(''); return }
    setPreviewUrl('')
    attachmentApi.getUrl(previewItem.id, false)
      .then((u) => { if (!cancelled) setPreviewUrl(u) })
      .catch(() => { if (!cancelled) message.error('无法加载预览') })
    return () => { cancelled = true }
  }, [previewItem])

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      await attachmentApi.upload(file, bizType, bizId)
      message.success('上传成功')
      fetchList()
    } catch (e) {
      const msg = e instanceof Error ? e.message : ''
      message.error(/failed to fetch|直传失败/i.test(msg) ? '直传失败，请检查对象存储的跨域(CORS)配置' : (msg || '上传失败'))
    } finally {
      setUploading(false)
    }
    return false
  }

  const handleDownload = async (item: AttachmentItem) => {
    try {
      const url = await attachmentApi.getUrl(item.id, true)
      const a = document.createElement('a')
      a.href = url
      a.target = '_blank'
      a.rel = 'noreferrer'
      a.download = item.original_name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } catch {
      message.error('下载失败')
    }
  }

  const handleDelete = async (item: AttachmentItem) => {
    Modal.confirm({
      title: '确认删除', content: `确定要删除附件「${item.original_name}」？`, okType: 'danger',
      onOk: async () => {
        await attachmentApi.delete(item.id)
        message.success('已删除')
        fetchList()
      },
    })
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  const previewType = previewItem ? isPreviewable(previewItem.content_type, previewItem.original_name) : false

  const columns = [
    { title: '文件名', dataIndex: 'original_name', render: (v: string, record: AttachmentItem) => {
      const pType = isPreviewable(record.content_type, record.original_name)
      return (
        <span className={pType ? 'cursor-pointer text-primary hover:underline' : ''} onClick={() => pType && setPreviewItem(record)}>
          {v}
        </span>
      )
    }},
    { title: '大小', dataIndex: 'file_size', width: 100, render: (v: number) => formatSize(v) },
    { title: '上传人', dataIndex: 'uploader_name', width: 100 },
    { title: '上传时间', dataIndex: 'created_at', width: 170,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', width: 140, render: (_: unknown, record: AttachmentItem) => (
      <div className="flex gap-3">
        {isPreviewable(record.content_type, record.original_name) && (
          <a onClick={() => setPreviewItem(record)} className="text-primary text-sm">
            <EyeOutlined /> 预览
          </a>
        )}
        <a onClick={() => handleDownload(record)} className="text-sm">
          <DownloadOutlined /> 下载
        </a>
        <a onClick={() => handleDelete(record)} className="text-rose-500 text-sm">
          <DeleteOutlined />
        </a>
      </div>
    ) },
  ]

  return (
    <div>
      <div className="flex justify-between mb-2">
        <span className="font-medium">附件</span>
        <Upload beforeUpload={handleUpload} showUploadList={false}>
          <Button size="small" icon={<UploadOutlined />} loading={uploading}>上传附件</Button>
        </Upload>
      </div>
      <Table rowKey="id" columns={columns} dataSource={list} loading={loading} pagination={false} size="small" />

      <Modal
        title={previewItem?.original_name || '预览'}
        open={!!previewItem}
        onCancel={() => setPreviewItem(null)}
        footer={null}
        width={previewType === 'pdf' ? 900 : 700}
        centered
      >
        {previewItem && !previewUrl && (
          <div className="flex justify-center items-center py-16 text-slate-400">加载中…</div>
        )}
        {previewItem && previewUrl && previewType === 'image' && (
          <div className="flex justify-center">
            <img src={previewUrl} alt={previewItem.original_name} className="max-w-full max-h-[70vh] object-contain" />
          </div>
        )}
        {previewItem && previewUrl && previewType === 'pdf' && (
          <iframe src={previewUrl} title={previewItem.original_name}
            className="w-full border-0 rounded" style={{ height: '70vh' }} />
        )}
      </Modal>
    </div>
  )
}
