import { useMemo } from 'react'
import { Button, Upload } from 'antd'
import { UploadOutlined, DeleteOutlined, PaperClipOutlined } from '@ant-design/icons'
import AttachmentPanel from '@/components/AttachmentPanel'
import { attachmentApi } from '@/api/attachment'
import { CONTRACT_ATTACHMENT_SLOTS, type RegAfterSlot } from '@/constants/contractRegistration'

/** bizType → 待上传文件（新建合同尚无 id 时用） */
export type PendingAttachments = Record<string, File[]>

export async function flushPendingAttachments(
  contractId: string,
  pending: PendingAttachments,
): Promise<{ ok: number; fail: number }> {
  let ok = 0
  let fail = 0
  for (const [bizType, files] of Object.entries(pending)) {
    for (const file of files || []) {
      try {
        await attachmentApi.upload(file, bizType, contractId)
        ok += 1
      } catch {
        fail += 1
      }
    }
  }
  return { ok, fail }
}

function PendingPanel({
  title,
  accept,
  files,
  onChange,
}: {
  title: string
  accept?: string
  files: File[]
  onChange: (files: File[]) => void
}) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
      <div className="flex justify-between mb-2 items-center">
        <span className="text-sm font-medium text-slate-700">{title}</span>
        <Upload
          multiple
          showUploadList={false}
          accept={accept}
          beforeUpload={(file) => {
            onChange([...files, file])
            return false
          }}
        >
          <Button size="small" icon={<UploadOutlined />}>
            {accept?.startsWith('image') ? '选择图片' : '选择文件'}
          </Button>
        </Upload>
      </div>
      {files.length === 0 ? (
        <div className="text-[12px] text-slate-400 py-2">尚未选择文件，创建后自动上传</div>
      ) : (
        <ul className="space-y-1">
          {files.map((f, i) => (
            <li key={`${f.name}-${f.size}-${i}`} className="flex items-center gap-2 text-[12px] text-slate-700">
              <PaperClipOutlined className="text-slate-400" />
              <span className="flex-1 truncate">{f.name}</span>
              <span className="text-slate-400 shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
              <Button
                type="text" size="small" danger icon={<DeleteOutlined />}
                onClick={() => onChange(files.filter((_, j) => j !== i))}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** 按简道云槽位渲染合同分类附件：有合同 id 直传；否则先暂存文件 */
export default function ContractAttachmentSlots({
  slot,
  contractId,
  pending,
  onPendingChange,
}: {
  slot: RegAfterSlot
  contractId?: string
  pending?: PendingAttachments
  onPendingChange?: (next: PendingAttachments) => void
}) {
  const panels = useMemo(() => CONTRACT_ATTACHMENT_SLOTS.filter((s) => s.key === slot), [slot])
  if (!panels.length) return null

  if (contractId) {
    return (
      <div className="space-y-3">
        {panels.map((p) => (
          <AttachmentPanel
            key={p.bizType}
            bizType={p.bizType}
            bizId={contractId}
            title={p.title}
            accept={p.accept}
            compact
          />
        ))}
      </div>
    )
  }

  if (!onPendingChange) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-[12px] text-slate-400 text-center">
        请选择文件：{panels.map((p) => p.title).join('、')}
      </div>
    )
  }

  const bag = pending || {}
  return (
    <div className="space-y-3">
      {panels.map((p) => (
        <PendingPanel
          key={p.bizType}
          title={p.title}
          accept={p.accept}
          files={bag[p.bizType] || []}
          onChange={(files) => {
            onPendingChange({ ...bag, [p.bizType]: files })
          }}
        />
      ))}
    </div>
  )
}
