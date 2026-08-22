import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Modal, Radio, Table, Input, Alert, Button, Space } from 'antd'
import { FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons'
import type { FieldSpec } from '@/components/ContractTerms'
import {
  applyPasteToGrid,
  emptyGridRows,
  getPasteableFields,
  gridToRows,
  parseClipboardText,
  rowsToGrid,
  validateQuickFillRows,
  type QuickFillIssue,
} from '@/utils/detailQuickFill'

type Row = Record<string, unknown>

export default function DetailQuickFillModal({
  open,
  title = '快速填报',
  fields,
  existingRows = [],
  onClose,
  onConfirm,
}: {
  open: boolean
  title?: string
  fields: FieldSpec[]
  existingRows?: Row[]
  onClose: () => void
  onConfirm: (rows: Row[], mode: 'append' | 'replace') => void
}) {
  const pasteable = useMemo(() => getPasteableFields(fields), [fields])
  const [mode, setMode] = useState<'append' | 'replace'>('append')
  const [step, setStep] = useState<1 | 2>(1)
  const [fullscreen, setFullscreen] = useState(false)
  const [grid, setGrid] = useState<string[][]>(() => emptyGridRows(pasteable.length))
  const [focus, setFocus] = useState({ row: 0, col: 0 })
  const [issues, setIssues] = useState<QuickFillIssue[]>([])
  const wrapRef = useRef<HTMLDivElement>(null)

  const resetGrid = useCallback((m: 'append' | 'replace') => {
    if (m === 'replace' && existingRows.length) {
      setGrid(rowsToGrid(existingRows, pasteable))
    } else {
      setGrid(emptyGridRows(pasteable.length))
    }
    setStep(1)
    setIssues([])
    setFocus({ row: 0, col: 0 })
  }, [existingRows, pasteable])

  useEffect(() => {
    if (!open) return
    setMode('append')
    resetGrid('append')
  }, [open, resetGrid])

  useEffect(() => {
    if (!open) return
    resetGrid(mode)
  }, [mode, open, resetGrid])

  const handlePaste = useCallback((e: ClipboardEvent) => {
    if (!open || step !== 1) return
    const text = e.clipboardData?.getData('text/plain') || ''
    if (!text.includes('\t') && !text.includes('\n')) return
    e.preventDefault()
    const matrix = parseClipboardText(text)
    setGrid((g) => applyPasteToGrid(g, matrix, focus.row, focus.col))
  }, [focus.col, focus.row, open, step])

  useEffect(() => {
    window.addEventListener('paste', handlePaste, true)
    return () => window.removeEventListener('paste', handlePaste, true)
  }, [handlePaste])

  const previewRows = useMemo(() => gridToRows(grid, pasteable), [grid, pasteable])

  const goNext = () => {
    const rows = gridToRows(grid, pasteable)
    if (!rows.length) return
    const errs = validateQuickFillRows(rows, fields)
    setIssues(errs)
    setStep(2)
  }

  const handleConfirm = () => {
    const rows = gridToRows(grid, pasteable)
    if (!rows.length) return
    onConfirm(rows, mode)
    onClose()
  }

  const updateCell = (ri: number, ci: number, val: string) => {
    setGrid((g) => g.map((row, i) => (i === ri ? row.map((c, j) => (j === ci ? val : c)) : row)))
  }

  const addRows = () => {
    setGrid((g) => [...g, ...emptyGridRows(pasteable.length, 5)])
  }

  const columns = [
    {
      title: '#',
      key: '__idx',
      width: 44,
      fixed: 'left' as const,
      render: (_: unknown, __: string[], i: number) => <span className="text-slate-400">{i + 1}</span>,
    },
    ...pasteable.map((f, ci) => ({
      title: (
        <span>
          {f.label}
          <span className="text-red-500 ml-0.5">*</span>
        </span>
      ),
      key: f.key,
      width: f.width || 120,
      render: (_: unknown, _row: string[], ri: number) => (
        <Input
          size="small"
          value={grid[ri]?.[ci] ?? ''}
          onFocus={() => setFocus({ row: ri, col: ci })}
          onChange={(e) => updateCell(ri, ci, e.target.value)}
          placeholder={f.kind === 'select' || f.kind === 'radio' ? '可选值' : ''}
        />
      ),
    })),
  ]

  return (
    <Modal
      open={open}
      title={title}
      onCancel={onClose}
      width={fullscreen ? '100vw' : 960}
      style={fullscreen ? { top: 0, padding: 0, maxWidth: '100vw' } : undefined}
      styles={fullscreen ? { body: { height: 'calc(100vh - 110px)', overflow: 'auto' } } : undefined}
      destroyOnClose
      footer={(
        <div className="flex items-center justify-between">
          <Button
            type="text"
            icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
            onClick={() => setFullscreen((v) => !v)}
          />
          <Space>
            {step === 2 && (
              <Button onClick={() => setStep(1)}>上一步</Button>
            )}
            <Button onClick={onClose}>取消</Button>
            {step === 1 ? (
              <Button type="primary" disabled={!previewRows.length} onClick={goNext}>下一步</Button>
            ) : (
              <Button type="primary" onClick={handleConfirm}>确定填入</Button>
            )}
          </Space>
        </div>
      )}
    >
      <div ref={wrapRef}>
        <Radio.Group
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="mb-3"
          optionType="button"
          buttonStyle="solid"
        >
          <Radio.Button value="append">新增记录</Radio.Button>
          <Radio.Button value="replace" disabled={!existingRows.length}>编辑已有记录</Radio.Button>
        </Radio.Group>

        {step === 1 ? (
          <>
            <Alert
              type="info"
              showIcon
              className="mb-3"
              message={(
                <ul className="list-disc pl-4 mb-0 text-[13px]">
                  <li>可将 Excel 内容粘贴到表格中，也可直接在表格内编辑；支持复制、粘贴、撤销与删除快捷键。</li>
                  <li>不支持粘贴的字段列已自动隐藏，请注意对应字段顺序。</li>
                </ul>
              )}
            />
            <Table
              size="small"
              bordered
              pagination={false}
              scroll={{ x: 'max-content', y: fullscreen ? 'calc(100vh - 320px)' : 360 }}
              rowKey={(_r, i) => String(i)}
              dataSource={grid}
              columns={columns}
            />
            <Button type="link" size="small" className="px-0 mt-1" onClick={addRows}>+ 添加 5 行</Button>
            <div className="text-[12px] text-slate-400 mt-1">
              提示：在任意单元格聚焦后 Ctrl+V 粘贴 Excel 区域；将按当前列顺序依次填入。
            </div>
          </>
        ) : (
          <>
            {issues.length > 0 && (
              <Alert
                type="warning"
                showIcon
                className="mb-3"
                message={`发现 ${issues.length} 处待核对项（仍可填入，提交时以表单校验为准）`}
                description={(
                  <ul className="list-disc pl-4 mb-0 max-h-28 overflow-auto text-[12px]">
                    {issues.slice(0, 20).map((it, i) => (
                      <li key={`${it.row}-${it.field}-${i}`}>
                        第 {it.row} 行 · {it.label}：{it.message}
                      </li>
                    ))}
                    {issues.length > 20 ? <li>…还有 {issues.length - 20} 条</li> : null}
                  </ul>
                )}
              />
            )}
            <Alert
              type="success"
              showIcon
              className="mb-3"
              message={`将${mode === 'append' ? '追加' : '替换为'} ${previewRows.length} 条明细`}
            />
            <Table
              size="small"
              bordered
              pagination={false}
              scroll={{ x: 'max-content', y: 280 }}
              rowKey={(_r, i) => String(i)}
              dataSource={previewRows}
              columns={fields.filter((f) => !f.computed || previewRows.some((r) => r[f.key] != null && r[f.key] !== '')).map((f) => ({
                title: f.label,
                key: f.key,
                width: f.width,
                render: (_: unknown, row: Row) => {
                  const v = row[f.key]
                  if (v == null || v === '') return <span className="text-slate-300">—</span>
                  if (f.options?.length) {
                    const hit = f.options.find((o) => o.value === String(v))
                    return hit?.label ?? String(v)
                  }
                  return String(v)
                },
              }))}
            />
          </>
        )}
      </div>
    </Modal>
  )
}
