import React from 'react'
import { ICON_MAP, ICON_FALLBACK } from './Icon'

// 移动端图标：与桌面端共用 components/Icon.tsx 的同一份「Material Symbols 名 -> antd 内联 SVG」
// 映射（打包进 JS、不依赖字体/网络，任何 webview 都能显示），保证各端图标语义一致。
//
// 与桌面端 <Icon> 的唯一差别：这里不加 app-icon 默认字号类。移动端有若干调用未显式指定尺寸，
// 沿用继承字号才能保持原有观感；桌面端则需要 24px 默认值以对齐原 .material-symbols-outlined。
export default function MobileIcon(
  { name, className, style }: { name?: string; className?: string; style?: React.CSSProperties },
) {
  const C = (name && ICON_MAP[name]) || ICON_FALLBACK
  return <C className={className} style={style} />
}
