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
  const [previewItem, setPreviewItem] = useState<AttachmentItem | null>(null)

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

  const handleUpload = async (file: File) => {
    await attachmentApi.upload(file, bizType, bizId)
    message.success('上传成功')
    fetchList()
    return false
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
  const previewUrl = previewItem ? `${attachmentApi.downloadUrl(previewItem.id)}?token=${localStorage.getItem('access_token') || ''}` : ''

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
        <a href={attachmentApi.downloadUrl(record.id)} target="_blank" rel="noreferrer" className="text-sm">
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
          <Button size="small" icon={<UploadOutlined />}>上传附件</Button>
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
        {previewItem && previewType === 'image' && (
          <div className="flex justify-center">
            <img src={previewUrl} alt={previewItem.original_name} className="max-w-full max-h-[70vh] object-contain" />
          </div>
        )}
        {previewItem && previewType === 'pdf' && (
          <iframe src={previewUrl} title={previewItem.original_name}
            className="w-full border-0 rounded" style={{ height: '70vh' }} />
        )}
      </Modal>
    </div>
  )
}
