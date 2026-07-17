// 扩展平台 → 仪表盘: 网格布局 + 编辑态(拖拽/缩放/加图表/配置数据源) + 保存。
import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import RGL, { WidthProvider, type Layout, type LayoutItem } from 'react-grid-layout/legacy'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import {
  Card, Button, Space, Typography, message, Modal, Form, Input, Select, Empty, Popconfirm,
} from 'antd'
import {
  ArrowLeftOutlined, PlusOutlined, EditOutlined, SaveOutlined, DeleteOutlined, DragOutlined,
} from '@ant-design/icons'
import { dashboardApi } from '@/api/lowcodeDashboard'
import { lowcodeApi } from '@/api/lowcode'
import type { Dashboard, DashComponent, ChartType, FieldDefinition, FormTemplate, CrmSource } from '@/types/lowcode'
import ChartWidget from '@/components/lowcode/ChartWidget'

const GridLayout = WidthProvider(RGL)
const { Title } = Typography
const genId = () => 'c' + Math.random().toString(36).slice(2, 8)
const CHART_TYPES = [
  { value: 'bar', label: '柱状图' }, { value: 'line', label: '折线图' },
  { value: 'area', label: '面积图' }, { value: 'pie', label: '饼图' },
  { value: 'funnel', label: '漏斗图' }, { value: 'radar', label: '雷达图' },
  { value: 'scatter', label: '散点图' }, { value: 'dual_axis', label: '双轴图' },
  { value: 'gauge', label: '仪表盘' }, { value: 'pivot', label: '透视表' },
  { value: 'number', label: '指标卡' },
]
const NUMERIC = new Set(['number', 'amount', 'formula'])
const DATE_TYPES = new Set(['date', 'datetime'])
const NO_DIM = new Set(['number', 'gauge'])          // 无需分组维度
const SERIES_TYPES = new Set(['bar', 'line', 'area', 'pivot'])  // 支持第二维度(多序列)
const TWO_METRIC = new Set(['scatter', 'dual_axis'])  // 需要两个指标
const METRIC_OPTS = [
  { label: '数量(count)', value: 'count' }, { label: '合计(sum)', value: 'sum' },
  { label: '平均(avg)', value: 'avg' }, { label: '最大(max)', value: 'max' }, { label: '最小(min)', value: 'min' },
]

export default function DashboardPage() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [dash, setDash] = useState<Dashboard | null>(null)
  const [components, setComponents] = useState<DashComponent[]>([])
  const [edit, setEdit] = useState(false)
  const [loading, setLoading] = useState(true)
  const [cfgOpen, setCfgOpen] = useState(false)

  useEffect(() => {
    (async () => {
      try { const r = await dashboardApi.get(id); setDash(r.data); setComponents(r.data.components || []) } finally { setLoading(false) }
    })()
  }, [id])

  const layout: LayoutItem[] = useMemo(() => components.map((c) => ({ i: c.id, x: c.layout.x, y: c.layout.y, w: c.layout.w, h: c.layout.h })), [components])

  const onLayoutChange = (l: Layout) => {
    if (!edit) return
    setComponents((prev) => prev.map((c) => {
      const li = l.find((x) => x.i === c.id)
      return li ? { ...c, layout: { x: li.x, y: li.y, w: li.w, h: li.h } } : c
    }))
  }

  const addComponent = (comp: DashComponent) => {
    const maxY = components.reduce((m, c) => Math.max(m, c.layout.y + c.layout.h), 0)
    setComponents([...components, { ...comp, layout: { x: 0, y: maxY, w: comp.type === 'number' ? 4 : 6, h: comp.type === 'number' ? 3 : 5 } }])
  }
  const removeComponent = (cid: string) => setComponents(components.filter((c) => c.id !== cid))

  const save = async () => {
    await dashboardApi.update(id, { components })
    message.success('已保存'); setEdit(false)
  }

  if (loading) return <Card loading />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/dashboards')}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>{dash?.name}</Title>
        </Space>
        <Space>
          {edit && <Button icon={<PlusOutlined />} onClick={() => setCfgOpen(true)}>添加图表</Button>}
          {edit
            ? <Button type="primary" icon={<SaveOutlined />} onClick={save}>保存</Button>
            : <Button icon={<EditOutlined />} onClick={() => setEdit(true)}>编辑</Button>}
        </Space>
      </div>

      {components.length === 0 ? (
        <Card><Empty description={edit ? '点「添加图表」开始搭建' : '空仪表盘,点「编辑」添加图表'} /></Card>
      ) : (
        <GridLayout className="layout" cols={12} rowHeight={60} layout={layout}
          isDraggable={edit} isResizable={edit} draggableHandle=".dash-drag" onLayoutChange={onLayoutChange} margin={[12, 12]}>
          {components.map((c) => (
            <div key={c.id} style={{ background: '#fff', border: '1px solid #f0f0f0', borderRadius: 8, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div className={edit ? 'dash-drag' : ''} style={{ padding: '6px 10px', borderBottom: '1px solid #f5f5f5', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: edit ? 'move' : 'default' }}>
                <span style={{ fontWeight: 500, fontSize: 13 }}>{edit && <DragOutlined style={{ marginRight: 6, color: '#bbb' }} />}{c.title}</span>
                {edit && (
                  <Popconfirm title="删除该图表?" onConfirm={() => removeComponent(c.id)}>
                    <DeleteOutlined style={{ color: '#ff4d4f', cursor: 'pointer' }} />
                  </Popconfirm>
                )}
              </div>
              <div style={{ flex: 1, minHeight: 0, padding: 8 }}><ChartWidget component={c} /></div>
            </div>
          ))}
        </GridLayout>
      )}

      <WidgetConfigModal open={cfgOpen} onClose={() => setCfgOpen(false)} onOk={(c) => { addComponent(c); setCfgOpen(false) }} />
    </div>
  )
}

function WidgetConfigModal({ open, onClose, onOk }: { open: boolean; onClose: () => void; onOk: (c: DashComponent) => void }) {
  const [form] = Form.useForm()
  const [forms, setForms] = useState<FormTemplate[]>([])
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [crmSources, setCrmSources] = useState<CrmSource[]>([])
  const chartType: ChartType = Form.useWatch('type', form) || 'bar'
  const sourceType: string = Form.useWatch('source_type', form) || 'form'
  const metricOp = Form.useWatch('metric_op', form) || 'count'
  const metricOp2 = Form.useWatch('metric_op2', form) || 'count'
  const dimField: string = Form.useWatch('dim_field', form)
  const crmEntity: string = Form.useWatch('crm_entity', form)

  useEffect(() => {
    if (!open) return
    form.resetFields()
    lowcodeApi.listTemplates({ pageNo: 1, pageSize: 100, published_only: true }).then((r) => setForms(r.data.items))
    dashboardApi.crmSources().then((r) => setCrmSources(r.data)).catch(() => setCrmSources([]))
    setFields([])
  }, [open])  // eslint-disable-line react-hooks/exhaustive-deps

  // CRM 数据源只有单一注册表指标, 无法支撑散点/双轴(需两个指标)→ 从类型列表剔除并复位无效选择。
  const typeOptions = sourceType === 'crm' ? CHART_TYPES.filter((t) => !TWO_METRIC.has(t.value)) : CHART_TYPES
  useEffect(() => {
    if (sourceType === 'crm' && TWO_METRIC.has(chartType)) form.setFieldValue('type', 'bar')
  }, [sourceType, chartType, form])

  const onFormChange = async (tid: string) => {
    form.setFieldsValue({ dim_field: undefined, metric_field: undefined })
    try { const v = await lowcodeApi.publishedVersion(tid); setFields((v.data.field_definitions as FieldDefinition[]) || []) } catch { setFields([]) }
  }

  const submit = async () => {
    const v = await form.validateFields()
    let data_source: DashComponent['data_source']
    if (v.source_type === 'crm') {
      const src = crmSources.find((s) => s.entity === v.crm_entity)
      const met = src?.metrics[v.crm_metric ?? 0]
      data_source = {
        source: 'crm', entity: v.crm_entity,
        dimensions: NO_DIM.has(v.type) ? [] : (v.crm_dim ? [{ field_id: v.crm_dim }] : []),
        metrics: [met ? { op: met.op as never, field_id: met.field } : { op: 'count' }],
      }
    } else {
      const dims: { field_id: string; granularity?: 'year' | 'month' | 'day' }[] = []
      // 仅当所选维度确为日期字段时才附带日期粒度: antd 会保留已卸载 Form.Item 的旧值,
      // 若从日期维度切到非日期维度, 直接读 v.dim_gran 会把粒度误加到非日期字段上导致错误分组。
      const dimIsDateField = DATE_TYPES.has(fields.find((f) => f.id === v.dim_field)?.type || '')
      if (!NO_DIM.has(v.type) && v.dim_field) dims.push({ field_id: v.dim_field, ...(dimIsDateField && v.dim_gran ? { granularity: v.dim_gran } : {}) })
      if (SERIES_TYPES.has(v.type) && v.dim_field2) dims.push({ field_id: v.dim_field2 })
      const metrics: { op: string; field_id?: string }[] = [{ op: v.metric_op, ...(v.metric_op === 'count' ? {} : { field_id: v.metric_field }) }]
      if (TWO_METRIC.has(v.type)) metrics.push({ op: v.metric_op2 || 'count', ...((v.metric_op2 || 'count') === 'count' ? {} : { field_id: v.metric_field2 }) })
      data_source = { source: 'form', template_id: v.template_id, dimensions: dims, metrics } as DashComponent['data_source']
    }
    onOk({ id: genId(), type: v.type, title: v.title, layout: { x: 0, y: 0, w: 6, h: 5 }, data_source })
  }

  const dimFields = fields.filter((f) => f.type !== 'detail_table')
  const numFields = fields.filter((f) => NUMERIC.has(f.type))
  const dimIsDate = DATE_TYPES.has(fields.find((f) => f.id === dimField)?.type || '')
  const crmSrc = crmSources.find((s) => s.entity === crmEntity)

  return (
    <Modal title="添加图表" open={open} onOk={submit} onCancel={onClose} destroyOnClose width={520}>
      <Form form={form} layout="vertical" initialValues={{ type: 'bar', metric_op: 'count', source_type: 'form' }}>
        <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}><Input placeholder="如: 各类别金额" /></Form.Item>
        <Form.Item name="type" label="图表类型"><Select options={typeOptions} /></Form.Item>
        <Form.Item name="source_type" label="数据来源类型">
          <Select options={[{ label: '自定义表单', value: 'form' }, { label: 'CRM 业务数据', value: 'crm' }]} />
        </Form.Item>

        {sourceType === 'form' ? (
          <>
            <Form.Item name="template_id" label="数据源(表单)" rules={[{ required: true, message: '请选择表单' }]}>
              <Select placeholder="选择已发布表单" options={forms.map((f) => ({ label: f.name, value: f.id }))} onChange={onFormChange} />
            </Form.Item>
            {!NO_DIM.has(chartType) && (
              <Form.Item name="dim_field" label="分组维度" rules={[{ required: true, message: '请选择维度字段' }]}>
                <Select placeholder="按哪个字段分组" options={dimFields.map((f) => ({ label: f.label, value: f.id }))} />
              </Form.Item>
            )}
            {!NO_DIM.has(chartType) && dimIsDate && (
              <Form.Item name="dim_gran" label="日期粒度" initialValue="month">
                <Select options={[{ label: '按年', value: 'year' }, { label: '按月', value: 'month' }, { label: '按日', value: 'day' }]} />
              </Form.Item>
            )}
            {SERIES_TYPES.has(chartType) && (
              <Form.Item name="dim_field2" label="第二维度(系列,可选)" tooltip="设置后按此维度拆分多条序列(多序列/透视表)">
                <Select allowClear placeholder="可选:按第二维度拆分序列"
                  options={dimFields.filter((f) => f.id !== dimField).map((f) => ({ label: f.label, value: f.id }))} />
              </Form.Item>
            )}
            <Form.Item name="metric_op" label={TWO_METRIC.has(chartType) ? '指标1 · 统计方式' : '统计方式'}>
              <Select options={METRIC_OPTS} />
            </Form.Item>
            {metricOp !== 'count' && (
              <Form.Item name="metric_field" label="统计字段(数值)" rules={[{ required: true, message: '请选择数值字段' }]}>
                <Select placeholder="对哪个数值字段统计" options={numFields.map((f) => ({ label: f.label, value: f.id }))} />
              </Form.Item>
            )}
            {TWO_METRIC.has(chartType) && (
              <>
                <Form.Item name="metric_op2" label="指标2 · 统计方式" initialValue="count">
                  <Select options={METRIC_OPTS} />
                </Form.Item>
                {metricOp2 !== 'count' && (
                  <Form.Item name="metric_field2" label="指标2 · 统计字段(数值)" rules={[{ required: true, message: '请选择数值字段' }]}>
                    <Select placeholder="第二个数值字段" options={numFields.map((f) => ({ label: f.label, value: f.id }))} />
                  </Form.Item>
                )}
              </>
            )}
          </>
        ) : (
          <>
            <Form.Item name="crm_entity" label="业务实体" rules={[{ required: true, message: '请选择业务实体' }]}>
              <Select placeholder="客户 / 线索 / 订单" options={crmSources.map((s) => ({ label: s.label, value: s.entity }))}
                onChange={() => form.setFieldsValue({ crm_dim: undefined, crm_metric: 0 })} />
            </Form.Item>
            {!NO_DIM.has(chartType) && (
              <Form.Item name="crm_dim" label="分组维度" rules={[{ required: true, message: '请选择维度' }]}>
                <Select placeholder="按哪个维度分组" options={(crmSrc?.dimensions || []).map((d) => ({ label: d.label, value: d.field }))} />
              </Form.Item>
            )}
            <Form.Item name="crm_metric" label="统计指标" initialValue={0}>
              <Select options={(crmSrc?.metrics || []).map((m, i) => ({ label: m.label, value: i }))} />
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  )
}
