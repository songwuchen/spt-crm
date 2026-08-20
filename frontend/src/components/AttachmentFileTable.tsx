import { useEffect, useMemo, useState } from 'react'
import { Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { attachmentApi } from '@/api/attachment'
import AttachmentFileActions from '@/components/AttachmentFileActions'
import {
  formatAttachmentSize,
  formatAttachmentTime,
  type AttachmentFileRow,
} from '@/utils/attachmentDisplay'
import { isMetaOnlyAttachmentId } from '@/utils/fileFieldValue'
import { useAttachmentPreview } from '@/hooks/useAttachmentPreview'
import { isPreviewable, canOpenAttachmentPreview } from '@/utils/attachmentPreview'

type Props = {
  items: AttachmentFileRow[]
  loading?: boolean
  /** 拉取大小/上传人/时间等元数据（低代码字段仅有 id+name 时） */
  fetchMeta?: boolean
  showDelete?: boolean
  onDelete?: (item: AttachmentFileRow) => void
  compact?: boolean
  emptyText?: string
}

function mergeMeta(base: AttachmentFileRow[], meta: AttachmentFileRow[]): AttachmentFileRow[] {
  const byId = new Map(meta.map((m) => [m.id, m]))
  return base.map((row) => {
    const m = byId.get(row.id)
    if (!m) return row
    return {
      ...row,
      name: row.name || m.name,
      content_type: m.content_type ?? row.content_type,
      file_size: m.file_size ?? row.file_size,
      uploader_name: m.uploader_name ?? row.uploader_name,
      created_at: m.created_at ?? row.created_at,
    }
  })
}

/** 简道云式附件列表：文件名 / 大小 / 上传人 / 上传时间 / 操作（预览·下载） */
export default function AttachmentFileTable({
  items,
  loading = false,
  fetchMeta = true,
  showDelete = false,
  onDelete,
  compact,
  emptyText = '暂无文件',
}: Props) {
  const { openPreview, download, previewModal } = useAttachmentPreview()
  const [metaLoading, setMetaLoading] = useState(false)
  const [rows, setRows] = useState<AttachmentFileRow[]>(items)

  useEffect(() => {
    setRows(items)
  }, [items])

  const realIds = useMemo(
    () => items.filter((i) => !i.metaOnly && !isMetaOnlyAttachmentId(i.id)).map((i) => i.id),
    [items],
  )

  useEffect(() => {
    if (!fetchMeta || !realIds.length) return
    let alive = true
    setMetaLoading(true)
    attachmentApi.listBatch(realIds)
      .then((list) => {
        if (!alive) return
        setRows(mergeMeta(items, list))
      })
      .catch(() => { /* 元数据失败仍展示 id+name */ })
      .finally(() => { if (alive) setMetaLoading(false) })
    return () => { alive = false }
  }, [fetchMeta, realIds.join('|'), items]) // eslint-disable-line react-hooks/exhaustive-deps

  const columns: ColumnsType<AttachmentFileRow> = [
    {
      title: '文件名',
      dataIndex: 'name',
      render: (v: string, record) => {
        const p = canOpenAttachmentPreview(record.name, record.content_type)
        return (
          <span
            className={p ? 'cursor-pointer text-teal-600 hover:underline' : undefined}
            onClick={() => p && openPreview(record)}
          >
            {v}
          </span>
        )
      },
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      width: 96,
      render: (v: number | undefined) => formatAttachmentSize(v),
    },
    {
      title: '上传人',
      dataIndex: 'uploader_name',
      width: 96,
      render: (v: string | undefined) => v || '—',
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      width: 168,
      render: (v: string | undefined) => formatAttachmentTime(v),
    },
    {
      title: '操作',
      key: 'op',
      width: showDelete ? 132 : 100,
      render: (_: unknown, record) => (
        <AttachmentFileActions
          item={record}
          onPreview={openPreview}
          onDownload={download}
          onDelete={onDelete}
          showDelete={showDelete}
        />
      ),
    },
  ]

  return (
    <>
      <Table
        rowKey="id"
        size="small"
        pagination={false}
        loading={loading || metaLoading}
        columns={columns}
        dataSource={rows}
        locale={{ emptyText }}
        className={compact ? 'attachment-file-table-compact' : undefined}
      />
      {previewModal}
    </>
  )
}
