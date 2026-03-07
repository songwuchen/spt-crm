import { useState, useCallback } from 'react'

interface PaginationState {
  page: number
  pageSize: number
  total: number
}

export function usePagination(defaultPageSize = 20) {
  const [state, setState] = useState<PaginationState>({ page: 1, pageSize: defaultPageSize, total: 0 })

  const setPage = useCallback((p: number) => setState(s => ({ ...s, page: p })), [])
  const setTotal = useCallback((t: number) => setState(s => ({ ...s, total: t })), [])
  const resetPage = useCallback(() => setState(s => ({ ...s, page: 1 })), [])

  const tableProps = {
    current: state.page,
    total: state.total,
    pageSize: state.pageSize,
    onChange: setPage,
    showTotal: (t: number) => `共 ${t} 条`,
  }

  return {
    page: state.page,
    pageSize: state.pageSize,
    total: state.total,
    setPage,
    setTotal,
    resetPage,
    tableProps,
  }
}
