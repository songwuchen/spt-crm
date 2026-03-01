import { useState, useEffect } from 'react'
import { Upload, Button, Table, message } from 'antd'
import { UploadOutlined, DownloadOutlined } from '@ant-design/icons'
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

export default function AttachmentPanel({ bizType, bizId }: Props) {
  const [list, setList] = useState<AttachmentItem[]>([])
  const [loading, setLoading] = useState(false)

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

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  const columns = [
    { title: '文件名', dataIndex: 'original_name' },
    { title: '大小', dataIndex: 'file_size', width: 100, render: (v: number) => formatSize(v) },
    { title: '上传人', dataIndex: 'uploader_name', width: 100 },
    { title: '上传时间', dataIndex: 'created_at', width: 170,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', width: 80, render: (_: unknown, record: AttachmentItem) => (
      <a href={attachmentApi.downloadUrl(record.id)} target="_blank" rel="noreferrer">
        <DownloadOutlined /> 下载
      </a>
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
    </div>
  )
}
