/** HTML 单据 → PDF Blob；边距对齐打印 @page（默认横向 5/8/3/8 mm）。 */
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

export type HtmlToPdfMargins = {
  top: number
  right: number
  bottom: number
  left: number
}

export type HtmlToPdfOptions = {
  orientation?: 'portrait' | 'landscape'
  fileName?: string
  /** html2canvas 缩放，越大越清晰，默认 2 */
  scale?: number
  /**
   * 页边距（mm）。默认对齐客户 Word 模板：
   * 上 5.3 / 右 7.8 / 下 0 / 左 7.9
   */
  margins?: HtmlToPdfMargins
}

/** 与客户 Word 模板页边距对齐（横向 297×210） */
export const DRAWING_PRINT_MARGINS: HtmlToPdfMargins = {
  top: 5.3,
  right: 7.8,
  bottom: 0,
  left: 7.9,
}

const MM_TO_PX = 96 / 25.4

function fileBase(html: string, fileName?: string): string {
  if (fileName?.trim()) return fileName.trim().replace(/\.(html?|pdf)$/i, '')
  const m = html.match(/<title[^>]*>([^<]*)<\/title>/i)
  const t = (m?.[1] || '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .trim()
  return (t || 'print').replace(/[\\/:*?"<>|]/g, '').replace(/\s+/g, '')
}

function injectPdfPageCss(
  html: string,
  pageWmm: number,
  pageHmm: number,
  m: HtmlToPdfMargins,
): string {
  const css = `
<style data-pdf-page>
  html, body {
    margin: 0 !important;
    padding: 0 !important;
    width: ${pageWmm}mm !important;
    height: ${pageHmm}mm !important;
    overflow: hidden !important;
    background: #fff !important;
  }
  body {
    /* 把 @page 边距落到屏幕渲染，html2canvas 才能截到白边 */
    padding: ${m.top}mm ${m.right}mm ${m.bottom}mm ${m.left}mm !important;
    box-sizing: border-box !important;
  }
  .sheet {
    width: 100% !important;
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
  }
  @page { size: ${pageWmm}mm ${pageHmm}mm; margin: 0; }
</style>`
  if (/<\/head>/i.test(html)) {
    return html.replace(/<\/head>/i, `${css}</head>`)
  }
  return `<!doctype html><html><head>${css}</head><body>${html}</body></html>`
}

/**
 * 把完整 HTML 文档渲染进离屏 iframe，按纸张尺寸截图写入 PDF。
 * 边距写入 HTML（与打印 @page 一致），再整页贴入 PDF，避免贴边或拉伸变形。
 */
export async function htmlToPdfBlob(
  html: string,
  opts?: HtmlToPdfOptions,
): Promise<{ blob: Blob; fileName: string }> {
  const landscape = opts?.orientation !== 'portrait'
  const scale = opts?.scale ?? 2
  const base = fileBase(html, opts?.fileName)
  const m = opts?.margins || DRAWING_PRINT_MARGINS

  const pageWmm = landscape ? 297 : 210
  const pageHmm = landscape ? 210 : 297
  const widthPx = Math.round(pageWmm * MM_TO_PX)
  const heightPx = Math.round(pageHmm * MM_TO_PX)

  const iframe = document.createElement('iframe')
  iframe.setAttribute('title', 'pdf-render')
  iframe.style.cssText = [
    'position:fixed',
    'left:-10000px',
    'top:0',
    `width:${widthPx}px`,
    `height:${heightPx}px`,
    'border:0',
    'opacity:0',
    'pointer-events:none',
    'background:#fff',
  ].join(';')
  document.body.appendChild(iframe)

  const win = iframe.contentWindow
  const doc = iframe.contentDocument || win?.document
  if (!win || !doc) {
    document.body.removeChild(iframe)
    throw new Error('无法创建打印渲染框')
  }

  doc.open()
  doc.write(injectPdfPageCss(html, pageWmm, pageHmm, m))
  doc.close()

  await new Promise<void>((resolve) => {
    if (doc.readyState === 'complete') {
      setTimeout(resolve, 120)
    } else {
      iframe.onload = () => setTimeout(resolve, 120)
      setTimeout(resolve, 500)
    }
  })

  try {
    // 截整页（含边距白边），尺寸锁定为纸张像素，避免内容贴边或被拉变形
    const canvas = await html2canvas(doc.documentElement, {
      scale,
      useCORS: true,
      backgroundColor: '#ffffff',
      width: widthPx,
      height: heightPx,
      windowWidth: widthPx,
      windowHeight: heightPx,
      x: 0,
      y: 0,
      scrollX: 0,
      scrollY: 0,
    })

    const pdf = new jsPDF({
      orientation: landscape ? 'landscape' : 'portrait',
      unit: 'mm',
      format: 'a4',
      compress: true,
    })
    // PNG 比 JPEG 更利于表格细线；整页 1:1 铺入，边距已在图里
    const img = canvas.toDataURL('image/png')
    pdf.addImage(img, 'PNG', 0, 0, pageWmm, pageHmm, undefined, 'FAST')
    const blob = pdf.output('blob')
    return { blob, fileName: `${base}.pdf` }
  } finally {
    if (iframe.parentNode) document.body.removeChild(iframe)
  }
}
