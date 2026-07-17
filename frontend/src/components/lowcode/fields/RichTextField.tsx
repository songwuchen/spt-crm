// 富文本字段 —— react-quill-new(snow 主题)。值为 HTML 字符串。
// 只读态经轻量清洗后渲染;编辑态提供常用工具栏。
import { useMemo } from 'react'
import ReactQuill from 'react-quill-new'
import 'react-quill-new/dist/quill.snow.css'

// 轻量清洗: 去除 script/style 块、on* 事件属性、javascript: 协议。
// 注: 富文本内容为本租户内用户录入,此处为纵深防御,非唯一防线。
export function sanitizeHtml(html: string): string {
  return (html || '')
    .replace(/<\s*(script|style)[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi, '')
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    .replace(/(href|src)\s*=\s*("|')\s*javascript:[^"']*\2/gi, '$1=$2#$2')
}

const MODULES = {
  toolbar: [
    [{ header: [1, 2, 3, false] }],
    ['bold', 'italic', 'underline', 'strike'],
    [{ list: 'ordered' }, { list: 'bullet' }],
    [{ color: [] }, { background: [] }],
    ['link'],
    ['clean'],
  ],
}

interface Props {
  value?: string | null
  onChange?: (v: string) => void
  readonly?: boolean
  placeholder?: string
}

export default function RichTextField({ value, onChange, readonly, placeholder }: Props) {
  const html = useMemo(() => sanitizeHtml(value || ''), [value])
  if (readonly) {
    return html
      ? <div className="ql-editor" style={{ padding: 0 }} dangerouslySetInnerHTML={{ __html: html }} />
      : <div style={{ paddingTop: 4, color: 'rgba(0,0,0,0.35)' }}>—</div>
  }
  return (
    <ReactQuill
      theme="snow" value={value || ''} modules={MODULES} placeholder={placeholder}
      onChange={(html, _delta, _source, editor) => {
        // Quill 空内容序列化为 '<p><br></p>'(非空字符串)→ 必填校验会误判为已填。
        // 无纯文本且无内嵌媒体时归一化为 '',让必填/空值判断正确。
        const hasText = editor.getText().trim().length > 0
        const hasEmbed = /<(img|iframe|video)\b/i.test(html)
        onChange?.(hasText || hasEmbed ? html : '')
      }}
    />
  )
}
