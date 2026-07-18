import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import fs from 'node:fs'
import path from 'node:path'
import Icon, { hasIcon } from '../Icon'
import MobileIcon from '../MobileIcon'

const SRC = path.resolve(__dirname, '../..')

function walk(dir: string, out: string[] = []): string[] {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    // 只扫生产源码：测试自身含有意造的未登记图标名(兜底用例)，会造成误报
    if (e.isDirectory()) {
      if (e.name !== '__tests__' && e.name !== 'test') walk(p, out)
    } else if (/\.(tsx|ts)$/.test(e.name) && !/\.test\.tsx?$/.test(e.name)) {
      out.push(p)
    }
  }
  return out
}

/**
 * 收集源码里所有「会传给 <Icon>/<MobileIcon> 的图标名字面量」。
 * 覆盖三种写法：name="x"、name={cond ? 'a' : 'b'}(三元里的字面量)、icon: 'x' / icon = 'x' 映射表与默认值。
 * 注意三元的条件项(如 status === 'approved')也会被抓进来,故断言时只校验「已登记的除外」用不了 ——
 * 这里改为收集后逐个断言,条件项恰好不是图标名时会误报,所以下面用白名单剔除已知的状态字面量。
 */
function collectIconNames(): Map<string, string[]> {
  const found = new Map<string, string[]>()
  const add = (n: string, where: string) => {
    if (!found.has(n)) found.set(n, [])
    found.get(n)!.push(where)
  }
  for (const file of walk(SRC)) {
    const src = fs.readFileSync(file, 'utf8')
    src.split('\n').forEach((line, i) => {
      const where = `${path.relative(SRC, file)}:${i + 1}`
      for (const m of line.matchAll(/<(?:Mobile)?Icon\s+name=("[a-z_0-9]+"|\{[^}]*\})/g)) {
        const v = m[1]
        if (v.startsWith('"')) add(v.slice(1, -1), where)
        else for (const q of v.matchAll(/'([a-z_0-9]+)'/g)) add(q[1], where)
      }
      for (const q of line.matchAll(/\bicon\s*(?::|=|\|\||\?\?)\s*'([a-z_0-9]+)'/g)) add(q[1], where)
    })
  }
  return found
}

// 三元条件里的业务状态字面量,会被上面的正则一并抓到,但它们不是图标名。
const NOT_ICON_NAMES = new Set([
  'approved', 'rejected', 'pending', 'cancelled', 'terminated', 'pass', 'high', 'urgent', 'dark',
])

describe('Icon', () => {
  it('把 Material Symbols 名映射到对应的 antd SVG 图标', () => {
    const { container } = render(<Icon name="search" />)
    expect(container.querySelector('.anticon-search')).toBeInTheDocument()
  })

  it('未登记的图标名回退到通用图标而不是崩溃', () => {
    const { container } = render(<Icon name="definitely_not_a_real_icon" />)
    expect(container.querySelector('.anticon-appstore')).toBeInTheDocument()
  })

  // 守住 index.css 的层叠顺序回归:app-icon 一旦跑到 utilities 之后,
  // 会把调用方的 text-sm/text-lg 全部盖成 24px。
  it('默认加 app-icon 字号类,并保留调用方的 className', () => {
    const { container } = render(<Icon name="search" className="text-sm mr-1" />)
    const el = container.querySelector('.anticon-search')!
    expect(el.className).toContain('app-icon')
    expect(el.className).toContain('text-sm')
    expect(el.className).toContain('mr-1')
  })

  it('移动端不加 app-icon(依赖继承字号,套 24px 会变大)', () => {
    const { container } = render(<MobileIcon name="search" className="text-sm" />)
    const el = container.querySelector('.anticon-search')!
    expect(el.className).not.toContain('app-icon')
    expect(el.className).toContain('text-sm')
  })

  it('app-icon 必须定义在 @layer base 内,否则会盖掉 Tailwind 的 text-*', () => {
    const css = fs.readFileSync(path.join(SRC, 'index.css'), 'utf8')
    const layerBase = css.match(/@layer\s+base\s*\{[\s\S]*?\n\}/g) || []
    expect(layerBase.some((b) => b.includes('.app-icon'))).toBe(true)
  })

  it('源码里用到的每个图标名都已登记(漏配会静默回退成通用图标)', () => {
    const missing: string[] = []
    for (const [name, wheres] of collectIconNames()) {
      if (NOT_ICON_NAMES.has(name)) continue
      if (!hasIcon(name)) missing.push(`${name} <- ${wheres[0]}`)
    }
    expect(missing).toEqual([])
  })
})
