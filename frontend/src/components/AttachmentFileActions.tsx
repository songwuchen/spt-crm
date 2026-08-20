import { EyeOutlined, DownloadOutlined, DeleteOutlined } from '@ant-design/icons'
import { canOpenAttachmentPreview } from '@/utils/attachmentPreview'
import type { AttachmentFileRow } from '@/utils/attachmentDisplay'
import { isMetaOnlyAttachmentId } from '@/utils/fileFieldValue'

/** 简道云式操作列：图标 + 文案竖排（阅览 / 下载 / 删除） */
export default function AttachmentFileActions({
  item,
  onPreview,
  onDownload,
  onDelete,
  showPreview = true,
  showDownload = true,
  showDelete = false,
}: {
  item: Pick<AttachmentFileRow, 'id' | 'name' | 'content_type' | 'metaOnly'>
  onPreview?: (item: AttachmentFileRow) => void
  onDownload?: (item: AttachmentFileRow) => void
  onDelete?: (item: AttachmentFileRow) => void
  showPreview?: boolean
  showDownload?: boolean
  showDelete?: boolean
}) {
  const row = item as AttachmentFileRow
  const previewable = showPreview && !!onPreview && !item.metaOnly
    && !isMetaOnlyAttachmentId(item.id)
    && canOpenAttachmentPreview(item.name, item.content_type)

  const actionCls = 'inline-flex min-w-[36px] cursor-pointer flex-col items-center text-[13px] leading-tight text-teal-600 hover:text-teal-700'

  return (
    <div className="inline-flex items-start gap-3">
      {previewable && onPreview && (
        <span className={actionCls} onClick={() => onPreview(row)} role="button" tabIndex={0}>
          <EyeOutlined className="mb-0.5 text-base" />
          阅览
        </span>
      )}
      {showDownload && onDownload && (
        <span className={actionCls} onClick={() => onDownload(row)} role="button" tabIndex={0}>
          <DownloadOutlined className="mb-0.5 text-base" />
          下载
        </span>
      )}
      {showDelete && onDelete && (
        <span
          className="inline-flex min-w-[36px] cursor-pointer flex-col items-center text-[13px] leading-tight text-rose-500 hover:text-rose-600"
          onClick={() => onDelete(row)}
          role="button"
          tabIndex={0}
        >
          <DeleteOutlined className="mb-0.5 text-base" />
          删除
        </span>
      )}
    </div>
  )
}
