import { useEffect, useMemo, useState } from 'react'
import { Button, Space, Tooltip } from 'antd'
import {
  EyeOutlined, DownloadOutlined, LeftOutlined, RightOutlined,
} from '@ant-design/icons'
import { attachmentApi } from '@/api/attachment'
import { useAttachmentPreview } from '@/hooks/useAttachmentPreview'
import {
  type AttachmentFileRow,
  downloadAttachmentFile,
} from '@/utils/attachmentDisplay'
import { shortAttachmentDisplayName } from '@/utils/attachmentDisplayName'
import { canOpenAttachmentPreview } from '@/utils/attachmentPreview'
import { isMetaOnlyAttachmentId, normalizeFileFieldValue } from '@/utils/fileFieldValue'

type Props = {
  value: unknown
  /** 缩略图尺寸 */
  thumbSize?: number
  /** 横向排列（明细表单元格）或网格（整行字段） */
  layout?: 'row' | 'grid'
  emptyText?: string
}

function toRows(value: unknown): AttachmentFileRow[] {
  return normalizeFileFieldValue(value).map((a) => ({
    id: a.id,
    name: a.name,
    metaOnly: a.metaOnly,
  }))
}

/** 只读图片/附件：缩略图条 + 画廊式上一张/下一张预览 */
export default function AttachmentGalleryReadonly({
  value,
  thumbSize = 72,
  layout = 'grid',
  emptyText = '—',
}: Props) {
  const rows = useMemo(() => toRows(value), [value])
  const { openGallery, download, previewModal } = useAttachmentPreview()
  const [urls, setUrls] = useState<Record<string, string>>({})
  const [meta, setMeta] = useState<Record<string, AttachmentFileRow>>({})

  const realIds = useMemo(
    () => rows.filter((r) => !r.metaOnly && !isMetaOnlyAttachmentId(r.id)).map((r) => r.id),
    [rows],
  )

  useEffect(() => {
    if (!realIds.length) return
    let alive = true
    void (async () => {
      try {
        const list = await attachmentApi.listBatch(realIds)
        if (!alive) return
        const byId: Record<string, AttachmentFileRow> = {}
        for (const m of list) byId[m.id] = m
        setMeta(byId)
      } catch { /* ignore */ }
    })()
    return () => { alive = false }
  }, [realIds.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!realIds.length) return
    let alive = true
    void (async () => {
      const next: Record<string, string> = {}
      for (const id of realIds.slice(0, 24)) {
        try {
          next[id] = await attachmentApi.getUrl(id, false)
        } catch { /* ignore */ }
      }
      if (alive) setUrls(next)
    })()
    return () => { alive = false }
  }, [realIds.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!rows.length) {
    return <span className="text-slate-400 text-sm">{emptyText}</span>
  }

  const merged = rows.map((r, i) => ({
    ...r,
    ...meta[r.id],
    displayName: shortAttachmentDisplayName(r.name, i),
  }))

  const previewable = merged.filter(
    (r) => !r.metaOnly && !isMetaOnlyAttachmentId(r.id)
      && canOpenAttachmentPreview(r.name, r.content_type),
  )

  const openAt = (id: string) => {
    const idx = previewable.findIndex((r) => r.id === id)
    if (idx < 0) return
    openGallery(previewable, idx)
  }

  const wrapCls = layout === 'row'
    ? 'flex flex-wrap items-start gap-2'
    : 'grid grid-cols-[repeat(auto-fill,minmax(88px,1fr))] gap-3'

  return (
    <>
      <div className={wrapCls}>
        {merged.map((r, i) => {
          const canPreview = !r.metaOnly && !isMetaOnlyAttachmentId(r.id)
            && canOpenAttachmentPreview(r.name, r.content_type)
          const thumb = urls[r.id]
          return (
            <div
              key={r.id}
              className="group flex flex-col items-stretch rounded-lg border border-slate-200 bg-slate-50/80 p-1.5"
              style={{ maxWidth: layout === 'row' ? thumbSize + 16 : undefined }}
            >
              <button
                type="button"
                className="relative overflow-hidden rounded-md border border-slate-200 bg-white"
                style={{ width: thumbSize, height: thumbSize }}
                onClick={() => (canPreview ? openAt(r.id) : download(r))}
                title={r.displayName}
              >
                {thumb ? (
                  <img
                    src={thumb}
                    alt={r.displayName}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-xs text-slate-400">
                    {canPreview ? '预览' : '文件'}
                  </span>
                )}
              </button>
              <Tooltip title={r.name}>
                <span className="mt-1 truncate text-center text-[11px] text-slate-600 px-0.5">
                  {r.displayName}
                </span>
              </Tooltip>
              <Space size={4} className="mt-1 justify-center opacity-90">
                {canPreview && (
                  <Button
                    type="link"
                    size="small"
                    className="!px-0 !h-auto text-[11px]"
                    icon={<EyeOutlined />}
                    onClick={() => openAt(r.id)}
                  >
                    阅览
                  </Button>
                )}
                {!r.metaOnly && !isMetaOnlyAttachmentId(r.id) && (
                  <Button
                    type="link"
                    size="small"
                    className="!px-0 !h-auto text-[11px]"
                    icon={<DownloadOutlined />}
                    onClick={() => download(r)}
                  >
                    下载
                  </Button>
                )}
              </Space>
            </div>
          )
        })}
      </div>
      {previewable.length > 1 && (
        <p className="mt-2 mb-0 text-xs text-slate-400">
          点击缩略图阅览，支持
          <LeftOutlined className="mx-0.5" />
          上一张 /
          <RightOutlined className="mx-0.5" />
          下一张切换（共 {previewable.length} 张）
        </p>
      )}
      {previewModal}
    </>
  )
}
