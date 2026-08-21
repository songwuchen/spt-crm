/** 列表 → 详情：记住当前页记录顺序，详情页上一条/下一条（对齐简道云） */
import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export type SiblingNavSnapshot = {
  ids: string[]
  total: number
  pageNo: number
  pageSize: number
  /** 列表筛选条件，翻页时原样带回 */
  listQuery?: Record<string, unknown>
  updatedAt: number
}

const PREFIX = 'crm:sibling-nav:'

function storageKey(scope: string) {
  return PREFIX + scope
}

export function rememberSiblingNav(
  scope: string,
  snap: {
    ids: string[]
    total: number
    pageNo: number
    pageSize: number
    listQuery?: Record<string, unknown>
  },
) {
  if (!scope || !snap.ids?.length) return
  try {
    const payload: SiblingNavSnapshot = {
      ids: snap.ids.filter(Boolean),
      total: snap.total,
      pageNo: snap.pageNo,
      pageSize: snap.pageSize,
      listQuery: snap.listQuery,
      updatedAt: Date.now(),
    }
    sessionStorage.setItem(storageKey(scope), JSON.stringify(payload))
  } catch { /* ignore quota */ }
}

export function readSiblingNav(scope: string): SiblingNavSnapshot | null {
  try {
    const raw = sessionStorage.getItem(storageKey(scope))
    if (!raw) return null
    const parsed = JSON.parse(raw) as SiblingNavSnapshot
    if (!parsed?.ids?.length) return null
    return parsed
  } catch {
    return null
  }
}

function writeSiblingNav(scope: string, snap: SiblingNavSnapshot) {
  try {
    sessionStorage.setItem(storageKey(scope), JSON.stringify({ ...snap, updatedAt: Date.now() }))
  } catch { /* ignore */ }
}

export type SiblingPageResult = {
  ids: string[]
  total: number
}

/**
 * 详情页：基于列表写入的 session 上下文翻上一条/下一条。
 * 边界翻页需传入 fetchPage。
 */
export function useSiblingRecordNav(
  scope: string,
  currentId: string | undefined,
  options: {
    pathForId: (id: string) => string
    /** 翻页时拉取该页 id 列表；不传则仅能在当前页内切换 */
    fetchPage?: (pageNo: number, snap: SiblingNavSnapshot) => Promise<SiblingPageResult | null>
  },
) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [tick, setTick] = useState(0)
  const pathForId = options.pathForId
  const fetchPage = options.fetchPage

  const snap = useMemo(() => {
    void tick
    return scope ? readSiblingNav(scope) : null
  }, [scope, tick, currentId])

  const localIndex = currentId && snap ? snap.ids.indexOf(currentId) : -1
  const globalIndex = localIndex >= 0 && snap
    ? (snap.pageNo - 1) * snap.pageSize + localIndex
    : -1
  const total = snap?.total ?? 0
  const hasNav = Boolean(snap && currentId && total > 0 && localIndex >= 0)

  const goRelative = useCallback(async (delta: -1 | 1) => {
    if (!scope || !currentId || busy) return
    const cur = readSiblingNav(scope)
    if (!cur) return
    const idx = cur.ids.indexOf(currentId)
    if (idx < 0) return

    const nextLocal = idx + delta
    if (nextLocal >= 0 && nextLocal < cur.ids.length) {
      navigate(pathForId(cur.ids[nextLocal]))
      return
    }

    if (!fetchPage) return
    const targetPage = cur.pageNo + delta
    const maxPage = Math.max(1, Math.ceil(cur.total / cur.pageSize) || 1)
    if (targetPage < 1 || targetPage > maxPage) return

    setBusy(true)
    try {
      const page = await fetchPage(targetPage, cur)
      if (!page?.ids?.length) return
      const nextSnap: SiblingNavSnapshot = {
        ids: page.ids,
        total: page.total,
        pageNo: targetPage,
        pageSize: cur.pageSize,
        listQuery: cur.listQuery,
        updatedAt: Date.now(),
      }
      writeSiblingNav(scope, nextSnap)
      setTick((n) => n + 1)
      const pick = delta > 0 ? page.ids[0] : page.ids[page.ids.length - 1]
      if (pick) navigate(pathForId(pick))
    } finally {
      setBusy(false)
    }
  }, [scope, currentId, busy, navigate, pathForId, fetchPage])

  return {
    hasNav,
    index: globalIndex,
    total,
    busy,
    goPrev: () => { void goRelative(-1) },
    goNext: () => { void goRelative(1) },
  }
}
