import { useState, useEffect } from 'react'
import { Upload, Button, Table, Modal, message } from 'antd'
import {
  UploadOutlined, DownloadOutlined, EyeOutlined, DeleteOutlined, InboxOutlined, PaperClipOutlined,
} from '@ant-design/icons'
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
  /** 业务 id；新建尚未落库时可为空，配合 pendingFiles 暂存 */
  bizId?: string
  /** 面板标题，默认「附件」 */
  title?: string
  /** 限制可选文件类型，如 image/* */
  accept?: string
  /** 紧凑模式（嵌入登记分区） */
  compact?: boolean
  /** 新建态暂存文件（无 bizId 时） */
  pendingFiles?: File[]
  onPendingChange?: (files: File[]) => void
}

function isPreviewable(contentType?: string, name?: string): 'image' | 'pdf' | false {
  if (!contentType && !name) return false
  const ct = (contentType || '').toLowerCase()
  const ext = (name || '').split('.').pop()?.toLowerCase()
  if (ct.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'].includes(ext || '')) return 'image'
  if (ct === 'application/pdf' || ext === 'pdf') return 'pdf'
  return false
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** 将新建时暂存的文件在业务 id 就绪后批量上传 */
export async function flushPendingAttachments(
  bizId: string,
  items: { bizType: string; files: File[] }[],
): Promise<{ ok: number; fail: number }> {
  let ok = 0
  let fail = 0
  for (const { bizType, files } of items) {
    for (const file of files || []) {
      try {
        await attachmentApi.upload(file, bizType, bizId)
        ok += 1
      } catch {
        fail += 1
      }
    }
  }
  return { ok, fail }
}

function PendingDropZone({
  title, accept, files, onChange, compact,
}: {
  title: string
  accept?: string
  files: File[]
  onChange: (files: File[]) => void
  compact?: boolean
}) {
  const isImage = accept?.startsWith('image')
  return (
    <div className={compact ? 'rounded-lg border border-slate-100 bg-slate-50/50 p-3' : 'mb-4'}>
      <div className="mb-2">
        <span className={compact ? 'text-sm font-medium text-slate-700' : 'font-medium'}>{title}</span>
      </div>
      <Upload.Dragger
        multiple
        showUploadList={false}
        accept={accept}
        beforeUpload={(file) => {
          onChange([...files, file])
          return false
        }}
        className="!bg-slate-50"
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined className="text-teal-600" />
        </p>
        <p className="ant-upload-text text-sm">
          {isImage ? '拖拽或点击选择图片，单张建议 20MB 以内' : '拖拽或点击选择文件'}
        </p>
        <p className="ant-upload-hint text-xs text-slate-400">保存后自动上传到本客户</p>
      </Upload.Dragger>
      {files.length > 0 && (
        <ul className="mt-2 space-y-1">
          {files.map((f, i) => (
            <li key={`${f.name}-${f.size}-${i}`} className="flex items-center gap-2 text-[12px] text-slate-700">
              <PaperClipOutlined className="text-slate-400" />
              <span className="flex-1 truncate">{f.name}</span>
              <span className="text-slate-400 shrink-0">{formatSize(f.size)}</span>
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => onChange(files.filter((_, j) => j !== i))}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function AttachmentPanel({
  bizType, bizId, title = '附件', accept, compact,
  pendingFiles, onPendingChange,
}: Props) {
  const [list, setList] = useState<AttachmentItem[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [previewItem, setPreviewItem] = useState<AttachmentItem | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string>('')

  // 新建态：无 bizId 时用本地暂存（对齐简道云创建即可选附件）
  if (!bizId) {
    if (!onPendingChange) {
      return (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-[12px] text-slate-400 text-center mb-4">
          保存后可上传{title}
        </div>
      )
    }
    return (
      <PendingDropZone
        title={title}
        accept={accept}
        files={pendingFiles || []}
        onChange={onPendingChange}
        compact={compact}
      />
    )
  }

  return (
    <AttachmentPanelBound
      bizType={bizType}
      bizId={bizId}
      title={title}
      accept={accept}
      compact={compact}
      list={list}
      setList={setList}
      loading={loading}
      setLoading={setLoading}
      uploading={uploading}
      setUploading={setUploading}
      previewItem={previewItem}
      setPreviewItem={setPreviewItem}
      previewUrl={previewUrl}
      setPreviewUrl={setPreviewUrl}
    />
  )
}

/** 有 bizId 时的列表面板（hooks 须在条件分支外的稳定组件里） */
function AttachmentPanelBound({
  bizType, bizId, title, accept, compact,
  list, setList, loading, setLoading, uploading, setUploading,
  previewItem, setPreviewItem, previewUrl, setPreviewUrl,
}: {
  bizType: string
  bizId: string
  title: string
  accept?: string
  compact?: boolean
  list: AttachmentItem[]
  setList: (v: AttachmentItem[]) => void
  loading: boolean
  setLoading: (v: boolean) => void
  uploading: boolean
  setUploading: (v: boolean) => void
  previewItem: AttachmentItem | null
  setPreviewItem: (v: AttachmentItem | null) => void
  previewUrl: string
  setPreviewUrl: (v: string) => void
}) {
  const fetchList = async () => {
    setLoading(true)
    try {
      const res = await client.get<unknown, ApiResponse<AttachmentItem[]>>('/api/v1/attachments/by_biz', {
        params: { biz_type: bizType, biz_id: bizId },
        headers: compact ? { 'X-Silent-Error': '1' } : undefined,
      })
      setList(res.data || [])
    } catch {
      setList([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchList() }, [bizType, bizId])

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
      if (msg === 'CORS_OR_NETWORK') {
        message.error('直传失败：浏览器无法连接对象存储，请检查 OSS 跨域(CORS)配置')
      } else {
        message.error(msg || '上传失败')
      }
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
    <div className={compact ? 'rounded-lg border border-slate-100 bg-slate-50/50 p-3' : ''}>
      <div className="flex justify-between mb-2 items-center">
        <span className={compact ? 'text-sm font-medium text-slate-700' : 'font-medium'}>{title}</span>
        <Upload beforeUpload={handleUpload} showUploadList={false} accept={accept}>
          <Button size="small" icon={<UploadOutlined />} loading={uploading}>
            {accept?.startsWith('image') ? '上传图片' : '上传附件'}
          </Button>
        </Upload>
      </div>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={list}
        loading={loading}
        pagination={false}
        size="small"
        locale={{ emptyText: '暂无文件，点击右上角上传' }}
      />

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
