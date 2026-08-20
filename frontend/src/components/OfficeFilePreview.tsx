import { useEffect, useRef, useState } from 'react'
import { renderAsync } from 'docx-preview'
import jsPreviewExcel from '@js-preview/excel'
import { init as initPptxPreview } from 'pptx-preview'
import '@js-preview/excel/lib/index.css'

type OfficeKind = 'word' | 'excel' | 'pptx'

const ERROR_LABEL: Record<OfficeKind, string> = {
  word: 'Word 文档',
  excel: 'Excel 表格',
  pptx: 'PPT 演示文稿',
}

/** Word / Excel / PPT 页内渲染（Blob → DOM） */
export default function OfficeFilePreview({
  kind,
  blob,
  height,
}: {
  kind: OfficeKind
  blob: Blob
  height: string
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const el = hostRef.current
    if (!el || !blob) return

    el.innerHTML = ''
    setError(false)
    let alive = true
    let cleanup: (() => void) | undefined

    void (async () => {
      try {
        if (kind === 'word') {
          await renderAsync(blob, el, undefined, {
            className: 'docx-preview-spt',
            inWrapper: true,
            ignoreWidth: false,
            ignoreHeight: false,
            breakPages: true,
          })
          return
        }
        if (kind === 'excel') {
          const viewer = jsPreviewExcel.init(el, { minColLength: 0, showContextmenu: false })
          cleanup = () => viewer.destroy()
          await viewer.preview(blob)
          return
        }
        const w = Math.max(el.clientWidth || 960, 640)
        const viewer = initPptxPreview(el, {
          width: w,
          height: Math.round(w * 9 / 16),
        })
        cleanup = () => viewer.destroy()
        await viewer.preview(await blob.arrayBuffer())
      } catch {
        if (alive) setError(true)
      }
    })()

    return () => {
      alive = false
      cleanup?.()
      el.innerHTML = ''
    }
  }, [kind, blob])

  if (error) {
    return (
      <div className="flex min-h-[240px] flex-col items-center justify-center px-6 py-10 text-center">
        <p className="mb-2 text-base font-medium text-slate-800">
          {ERROR_LABEL[kind]}渲染失败
        </p>
        <p className="mb-0 text-sm text-slate-500">请下载后在 Office / WPS 中打开。</p>
      </div>
    )
  }

  return (
    <div
      className="overflow-auto rounded border border-slate-100 bg-white"
      style={{ height, minHeight: 360 }}
    >
      <div
        ref={hostRef}
        className={
          kind === 'word'
            ? 'docx-preview-host p-4'
            : kind === 'excel'
              ? 'excel-preview-host min-h-full'
              : 'pptx-preview-host min-h-full py-2'
        }
      />
    </div>
  )
}
