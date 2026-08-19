/**
 * 对齐简道云的上传虚线区：「选择」+ 拖拽 / 单击后粘贴。
 * FileField、AttachmentPanel 共用，避免两套 UI。
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Spin } from 'antd'

const FILE_MAX = 50 * 1024 * 1024
const IMAGE_MAX = 20 * 1024 * 1024

/** 截图/复制文件多在 items 里，files 可能为空 */
export function filesFromClipboard(data: DataTransfer | null | undefined): File[] {
  if (!data) return []
  const out: File[] = []
  const seen = new Set<string>()
  const push = (f: File | null) => {
    if (!f) return
    const key = `${f.name}|${f.size}|${f.type}|${f.lastModified}`
    if (seen.has(key)) return
    seen.add(key)
    out.push(f)
  }
  if (data.items?.length) {
    for (const item of Array.from(data.items)) {
      if (item.kind === 'file') push(item.getAsFile())
    }
  }
  if (!out.length && data.files?.length) {
    for (const f of Array.from(data.files)) push(f)
  }
  return out
}

export function jdyUploadHint(image?: boolean, inCellPopover?: boolean): string {
  if (image && inCellPopover) return '拖拽或Ctrl+v粘贴图片，单张20MB以内'
  return image
    ? '拖拽或单击后粘贴图片，单张20MB以内'
    : '拖拽或单击后粘贴文件（含 PDF/OFD/CAD 等），单个50MB以内'
}

export function jdyMaxBytes(image?: boolean): number {
  return image ? IMAGE_MAX : FILE_MAX
}

type Props = {
  image?: boolean
  disabled?: boolean
  uploading?: boolean
  /** 窄列（lineWidth≤3）：仅「选择 + 暂无内容」，避免同排字段被虚线区撑出重叠 */
  compact?: boolean
  /** 明细表单元格 Popover 内：简道云式 Ctrl+v 提示 */
  inCellPopover?: boolean
  /** 校验并接收文件（由父组件负责上传或暂存） */
  onFiles: (files: File[]) => void | Promise<void>
  extraRight?: ReactNode
  className?: string
}

export function jdyUploadHintShort(image?: boolean): string {
  return image ? '粘贴图片' : '粘贴文件'
}

export default function JdyUploadZone({
  image, disabled, uploading, compact, inCellPopover, onFiles, extraRight, className,
}: Props) {
  const [dragOver, setDragOver] = useState(false)
  const [focused, setFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const zoneRef = useRef<HTMLDivElement>(null)
  const hint = compact ? jdyUploadHintShort(image) : jdyUploadHint(image, inCellPopover)

  const takeFiles = (files: File[]) => {
    if (disabled || !files.length) return
    void onFiles(files)
  }

  useEffect(() => {
    if (!focused || disabled) return
    const onPaste = (e: ClipboardEvent) => {
      const files = filesFromClipboard(e.clipboardData)
      if (!files.length) return
      e.preventDefault()
      e.stopPropagation()
      takeFiles(files)
    }
    window.addEventListener('paste', onPaste, true)
    return () => window.removeEventListener('paste', onPaste, true)
  }, [focused, disabled, image]) // eslint-disable-line react-hooks/exhaustive-deps

  const rowFixed = inCellPopover && !!extraRight
  const zoneMinH = compact ? 'min-h-[32px]' : rowFixed ? 'h-full min-h-0' : 'min-h-[40px]'
  const zonePad = compact ? 'px-2 py-1' : rowFixed ? 'h-full px-3 py-0' : 'px-3 py-2'

  return (
    <div
      className={[
        'flex w-full min-w-0 max-w-full gap-2',
        rowFixed ? 'h-10 items-stretch' : 'items-stretch',
        className,
      ].filter(Boolean).join(' ')}
    >
      <div
        ref={zoneRef}
        tabIndex={disabled ? -1 : 0}
        role="button"
        className={[
          'flex min-w-0 flex-1 cursor-text items-center gap-2 rounded border border-dashed outline-none transition-colors',
          zoneMinH,
          zonePad,
          disabled
            ? 'cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400'
            : dragOver || focused
              ? compact || rowFixed
                ? 'border-teal-500 bg-teal-50/60 ring-1 ring-inset ring-teal-200'
                : 'border-teal-500 bg-teal-50/60 ring-2 ring-teal-200'
              : 'border-slate-300 bg-white hover:border-teal-400',
        ].join(' ')}
        onClick={() => {
          if (disabled) return
          zoneRef.current?.focus()
        }}
        onFocus={() => { if (!disabled) setFocused(true) }}
        onBlur={() => setFocused(false)}
        onKeyDown={(e) => {
          if (disabled) return
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragEnter={(e) => { e.preventDefault(); if (!disabled) setDragOver(true) }}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (disabled) return
          takeFiles(Array.from(e.dataTransfer.files || []))
        }}
      >
        <span
          className={[
            'shrink-0 text-[13px] font-medium',
            disabled ? 'text-slate-400' : 'cursor-pointer text-teal-600 hover:text-teal-700',
          ].join(' ')}
          onMouseDown={(e) => e.preventDefault()}
          onClick={(e) => {
            e.stopPropagation()
            if (disabled) return
            inputRef.current?.click()
          }}
        >
          选择
        </span>
        <span className="min-w-0 flex-1 truncate text-[12px] text-slate-400">
          {focused && !disabled
            ? (image ? '可 Ctrl+V 粘贴' : '可 Ctrl+V 粘贴')
            : (compact && !focused && !disabled ? '暂无内容' : hint)}
        </span>
        {uploading && <Spin size="small" />}
          <input
            ref={inputRef}
            type="file"
            multiple
            disabled={disabled}
            accept={image ? 'image/*' : undefined}
            style={{ display: 'none' }}
            onChange={(e) => {
              const files = e.target.files
              if (files?.length) takeFiles(Array.from(files))
              e.target.value = ''
            }}
          />
      </div>
      {extraRight ? (
        <div className={rowFixed ? 'flex h-full w-10 shrink-0' : 'flex shrink-0 items-stretch'}>
          {extraRight}
        </div>
      ) : null}
    </div>
  )
}
