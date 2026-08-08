/** 打印独立 HTML 单据（不打印当前 SPA 页面）。 */

export function escHtml(val: unknown): string {
  return String(val ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string),
  )
}

export type PrintHtmlOptions = {
  /** 排版预览用纸向；与单据 @page 一致。默认纵向 */
  orientation?: 'portrait' | 'landscape'
  /**
   * 另存 PDF / 下载时的文件名（不含 .pdf）。
   * 浏览器 iframe 打印会沿用当前 SPA 页标题，需临时改 document.title。
   */
  fileName?: string
}

function printFileBaseName(html: string, fileName?: string): string {
  if (fileName?.trim()) return fileName.trim().replace(/\.(html?|pdf)$/i, '')
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  const t = (m?.[1] || '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .trim()
  return t || 'print'
}

/** 打印期间临时改顶层标题，使「另存为 PDF」用业务文件名而非「方案管理 - SPT-CRM」 */
function withTempDocumentTitle(title: string, run: () => void): void {
  const name = title.trim()
  if (!name) {
    run()
    return
  }
  const prev = document.title
  document.title = name
  let restored = false
  const restore = () => {
    if (restored) return
    restored = true
    document.title = prev
    window.removeEventListener('afterprint', restore)
  }
  window.addEventListener('afterprint', restore)
  try {
    run()
  } catch (e) {
    restore()
    throw e
  }
  // afterprint 在部分环境（含个别 WPS）不稳定，延迟兜底
  setTimeout(restore, 120_000)
}

/**
 * Chromium 对 width/height=0 的 iframe + srcdoc 打印常出空白页。
 * 这里用离屏 A4 尺寸 iframe + document.write，必要时再开新窗口。
 */
export function printHtml(html: string, opts?: PrintHtmlOptions): void {
  const landscape = opts?.orientation === 'landscape'
  const fileName = printFileBaseName(html, opts?.fileName)
  // A4：纵向 210×297，横向 297×210
  const width = landscape ? '297mm' : '210mm'
  const height = landscape ? '210mm' : '297mm'
  const iframe = document.createElement('iframe')
  iframe.setAttribute('title', fileName || 'print-frame')
  // 必须有实际排版尺寸，否则预览空白
  iframe.style.cssText = [
    'position:fixed',
    'left:-10000px',
    'top:0',
    `width:${width}`,
    `height:${height}`,
    'border:0',
    'opacity:0',
    'pointer-events:none',
  ].join(';')
  document.body.appendChild(iframe)

  const win = iframe.contentWindow
  const doc = iframe.contentDocument || win?.document
  if (!win || !doc) {
    document.body.removeChild(iframe)
    printHtmlViaWindow(html, fileName)
    return
  }

  doc.open()
  doc.write(html)
  doc.close()
  try {
    doc.title = fileName
  } catch { /* ignore */ }

  const doPrint = () => {
    withTempDocumentTitle(fileName, () => {
      try {
        win.focus()
        win.print()
      } catch {
        printHtmlViaWindow(html, fileName)
      } finally {
        setTimeout(() => {
          if (iframe.parentNode) document.body.removeChild(iframe)
        }, 1500)
      }
    })
  }

  // 等样式/布局就绪再打，避免空白预览
  if (doc.readyState === 'complete') {
    setTimeout(doPrint, 50)
  } else {
    iframe.onload = () => setTimeout(doPrint, 50)
    setTimeout(doPrint, 300) // 兜底
  }
}

function printHtmlViaWindow(html: string, fileName?: string): void {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const base = printFileBaseName(html, fileName)
  const w = window.open(url, '_blank')
  if (!w) {
    // 弹窗被拦时退回下载，至少能看见内容
    const a = document.createElement('a')
    a.href = url
    a.download = `${base}.html`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 30_000)
    return
  }
  const finish = () => {
    try {
      try { w.document.title = base } catch { /* ignore */ }
      // 新窗口自带 title；同时改顶层，兼容部分打印驱动读 opener 标题
      withTempDocumentTitle(base, () => {
        w.focus()
        w.print()
      })
    } finally {
      // 等用户关打印框再关窗口，避免另存 PDF 时窗口已关丢标题
      setTimeout(() => {
        try { w.close() } catch { /* ignore */ }
        URL.revokeObjectURL(url)
      }, 60_000)
    }
  }
  // blob 窗口 load 时机不稳定
  setTimeout(finish, 200)
}
