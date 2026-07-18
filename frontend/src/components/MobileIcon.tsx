import React from 'react'
import Icon from './Icon'

// 移动端图标：与桌面端共用 components/Icon.tsx 的同一份映射与组件，仅关掉 24px 默认字号
// —— 移动端多处调用不指定尺寸、依赖继承字号，套上默认值会变大。
// 保留这个薄封装是为了让 28 个移动端页面的 import 不必改动。
export default function MobileIcon(
  props: { name?: string; className?: string; style?: React.CSSProperties },
) {
  return <Icon {...props} defaultSize={false} />
}
