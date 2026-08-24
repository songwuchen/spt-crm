import { useState, useEffect } from 'react'
import { Button, Modal, message } from 'antd'
import { DeleteOutlined, PaperClipOutlined } from '@ant-design/icons'
import { attachmentApi } from '@/api/attachment'
import AttachmentFileTable from '@/components/AttachmentFileTable'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { formatAttachmentSize } from '@/utils/attachmentDisplay'
import type { AttachmentFileRow } from '@/utils/attachmentDisplay'
import JdyUploadZone, { jdyMaxBytes } from '@/components/lowcode/fields/JdyUploadZone'

interface AttachmentItem extends AttachmentFileRow {
  file_size: number
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
  /** 审批/只读：不展示上传与删除，仅预览下载 */
  readonly?: boolean
  /** 新建态暂存文件（无 bizId 时） */
  pendingFiles?: File[]
  onPendingChange?: (files: File[]) => void
}

function formatSize(bytes: number) {
  return formatAttachmentSize(bytes)
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
  const isImage = !!accept?.startsWith('image')
  const maxBytes = jdyMaxBytes(isImage)

  const take = (incoming: File[]) => {
    const next = [...files]
    for (const file of incoming) {
      if (isImage && !file.type.startsWith('image/')) {
        message.warning('请选择图片文件')
        continue
      }
      if (file.size > maxBytes) {
        message.warning(isImage ? '单张图片不能超过 20MB' : '单个文件不能超过 200MB')
        continue
      }
      next.push(file)
    }
    onChange(next)
  }

  return (
    <div className={compact ? 'rounded-lg border border-slate-100 bg-slate-50/50 p-3' : 'mb-4'}>
      <div className="mb-2">
        <span className={compact ? 'text-sm font-medium text-slate-700' : 'font-medium'}>{title}</span>
      </div>
      <JdyUploadZone image={isImage} onFiles={take} />
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
  bizType, bizId, title = '附件', accept, compact, readonly,
  pendingFiles, onPendingChange,
}: Props) {
  const [list, setList] = useState<AttachmentItem[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  // 新建态：无 bizId 时用本地暂存（对齐简道云创建即可选附件）
  if (!bizId) {
    if (readonly || !onPendingChange) {
      return (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-[12px] text-slate-400 text-center mb-4">
          {readonly ? `暂无${title}` : `保存后可上传${title}`}
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
      readonly={!!readonly}
      list={list}
      setList={setList}
      loading={loading}
      setLoading={setLoading}
      uploading={uploading}
      setUploading={setUploading}
      loadError={loadError}
      setLoadError={setLoadError}
    />
  )
}

/** 有 bizId 时的列表面板（hooks 须在条件分支外的稳定组件里） */
function AttachmentPanelBound({
  bizType, bizId, title, accept, compact, readonly,
  list, setList, loading, setLoading, uploading, setUploading,
  loadError, setLoadError,
}: {
  bizType: string
  bizId: string
  title: string
  accept?: string
  compact?: boolean
  readonly?: boolean
  list: AttachmentItem[]
  setList: (v: AttachmentItem[]) => void
  loading: boolean
  setLoading: (v: boolean) => void
  uploading: boolean
  setUploading: (v: boolean) => void
  loadError: string | null
  setLoadError: (v: string | null) => void
}) {
  const isImage = !!accept?.startsWith('image')
  const maxBytes = jdyMaxBytes(isImage)

  const fetchList = async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const res = await client.get<unknown, ApiResponse<Array<{
        id: string
        original_name: string
        content_type?: string
        file_size: number
        uploader_name?: string
        created_at: string
      }>>>('/api/v1/attachments/by_biz', {
        params: { biz_type: bizType, biz_id: bizId },
        // 只读审批态需要看到失败原因；编辑紧凑态仍静默
        headers: compact && !readonly ? { 'X-Silent-Error': '1' } : undefined,
      })
      setList((res.data || []).map((a) => ({
        id: a.id,
        name: a.original_name,
        content_type: a.content_type,
        file_size: a.file_size,
        uploader_name: a.uploader_name,
        created_at: a.created_at,
      })))
    } catch {
      setList([])
      setLoadError('附件加载失败（可能无权限），请刷新或联系管理员')
      if (!compact) message.error('附件列表加载失败，请刷新重试')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchList() }, [bizType, bizId])

  const handleUploadMany = async (files: File[]) => {
    setUploading(true)
    try {
      for (const file of files) {
        if (isImage && !file.type.startsWith('image/')) {
          message.warning('请选择图片文件')
          continue
        }
        if (file.size > maxBytes) {
          message.warning(isImage ? '单张图片不能超过 20MB' : '单个文件不能超过 200MB')
          continue
        }
        try {
          await attachmentApi.upload(file, bizType, bizId)
        } catch (e) {
          const msg = e instanceof Error ? e.message : ''
          if (msg === 'CORS_OR_NETWORK') {
            message.error('直传失败：浏览器无法连接对象存储，请检查 OSS 跨域(CORS)配置')
          } else {
            message.error(msg || '上传失败')
          }
        }
      }
      await fetchList()
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (item: AttachmentFileRow) => {
    Modal.confirm({
      title: '确认删除', content: `确定要删除附件「${item.name}」？`, okType: 'danger',
      onOk: async () => {
        await attachmentApi.delete(item.id)
        message.success('已删除')
        fetchList()
      },
    })
  }

  return (
    <div className={compact ? 'rounded-lg border border-slate-100 bg-slate-50/50 p-3' : 'mb-4'}>
      <div className="mb-2">
        <span className={compact ? 'text-sm font-medium text-slate-700' : 'font-medium'}>{title}</span>
      </div>
      {!readonly && (
        <JdyUploadZone image={isImage} uploading={uploading} onFiles={handleUploadMany} />
      )}
      {loadError ? (
        <div className="mt-2 text-[12px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
          {loadError}
        </div>
      ) : (
        <div className={readonly ? undefined : 'mt-2'}>
          <AttachmentFileTable
            items={list}
            loading={loading}
            fetchMeta={false}
            showDelete={!readonly}
            onDelete={readonly ? undefined : handleDelete}
            compact={compact}
            emptyText={readonly ? '暂无附件' : '暂无文件'}
          />
        </div>
      )}
    </div>
  )
}
