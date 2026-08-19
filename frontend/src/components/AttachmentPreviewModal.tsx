import { Modal } from 'antd'
import type { PreviewableKind } from '@/utils/attachmentPreview'

type Props = {
  open: boolean
  title?: string
  url: string
  kind: PreviewableKind | false
  loading?: boolean
  onClose: () => void
}

/** 页内预览附件（图片 / PDF），对齐简道云查看体验。 */
export default function AttachmentPreviewModal({
  open, title, url, kind, loading, onClose,
}: Props) {
  return (
    <Modal
      title={title || '预览'}
      open={open}
      onCancel={onClose}
      footer={null}
      width={kind === 'pdf' ? 900 : 720}
      centered
      destroyOnClose
    >
      {loading && (
        <div className="flex items-center justify-center py-16 text-slate-400">加载中…</div>
      )}
      {!loading && kind === 'image' && url && (
        <div className="flex justify-center">
          <img src={url} alt={title || '预览'} className="max-h-[70vh] max-w-full object-contain" />
        </div>
      )}
      {!loading && kind === 'pdf' && url && (
        <iframe
          src={url}
          title={title || 'PDF 预览'}
          className="w-full rounded border-0"
          style={{ height: '70vh' }}
        />
      )}
    </Modal>
  )
}
