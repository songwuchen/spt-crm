/** 打印独立 HTML 单据（不打印当前 SPA 页面）。 */

export function escHtml(val: unknown): string {
  return String(val ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string),
  )
}

export type PrintHtmlOptions = {
  /** 排版预览用纸向；与单据 @page 一致。默认纵向 */
  orientation?: 'portrait' | 'landscape'
}

/**
 * Chromium 对 width/height=0 的 iframe + srcdoc 打印常出空白页，
 * 且弹窗标题会变成当前业务页（如「方案管理 - SPT-CRM」）。
 * 这里用离屏 A4 尺寸 iframe + document.write，必要时再开新窗口。
 */
export function printHtml(html: string, opts?: PrintHtmlOptions): void {
  const landscape = opts?.orientation === 'landscape'
  // A4：纵向 210×297，横向 297×210
  const width = landscape ? '297mm' : '210mm'
  const height = landscape ? '210mm' : '297mm'
  const iframe = document.createElement('iframe')
  iframe.setAttribute('title', 'print-frame')
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
    printHtmlViaWindow(html)
    return
  }

  doc.open()
  doc.write(html)
  doc.close()

  const doPrint = () => {
    try {
      win.focus()
      win.print()
    } catch {
      printHtmlViaWindow(html)
    } finally {
      setTimeout(() => {
        if (iframe.parentNode) document.body.removeChild(iframe)
      }, 1500)
    }
  }

  // 等样式/布局就绪再打，避免空白预览
  if (doc.readyState === 'complete') {
    setTimeout(doPrint, 50)
  } else {
    iframe.onload = () => setTimeout(doPrint, 50)
    setTimeout(doPrint, 300) // 兜底
  }
}

function printHtmlViaWindow(html: string): void {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const w = window.open(url, '_blank')
  if (!w) {
    URL.revokeObjectURL(url)
    // 弹窗被拦时退回下载，至少能看见内容
    const a = document.createElement('a')
    a.href = url
    a.download = 'print.html'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 30_000)
    return
  }
  const finish = () => {
    try {
      w.focus()
      w.print()
    } finally {
      setTimeout(() => {
        try { w.close() } catch { /* ignore */ }
        URL.revokeObjectURL(url)
      }, 800)
    }
  }
  // blob 窗口 load 时机不稳定
  setTimeout(finish, 200)
}
