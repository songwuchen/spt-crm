import { useState, useEffect } from 'react'
import {
  Table, Button, Input, Space, Select, Modal, Form, InputNumber, DatePicker, message, Tag, Drawer, Upload, Alert,
} from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, BarChartOutlined, UploadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { measurementApi } from '@/api/measurement'
import type { ServiceMeasurement, MeasurementModelStat } from '@/api/types'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useCustomerSelect } from '@/hooks/useSelectOptions'

const INDUSTRY_OPTIONS = ['冶金', '矿山', '煤炭', '电厂', '化工', '砂石骨料', '其他'].map(v => ({ label: v, value: v }))
const RATING = ['优秀', '一般', '差'].map(v => ({ label: v, value: v }))
const PRODUCT_RATING = ['满意', '一般', '不满意'].map(v => ({ label: v, value: v }))
const num = (v?: number) => (v != null ? v : '-')

export default function MeasurementPage() {
  usePageTitle('售后实测数据')
  const [data, setData] = useState<ServiceMeasurement[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [industry, setIndustry] = useState<string | undefined>()
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ServiceMeasurement | null>(null)
  const [form] = Form.useForm()
  const customerSelect = useCustomerSelect()
  const [statsOpen, setStatsOpen] = useState(false)
  const [stats, setStats] = useState<MeasurementModelStat[]>([])
  // 批量导入
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ success: number; failed: number; total: number; errors: { row: number; reason: string }[] } | null>(null)

  const doImport = async () => {
    if (!importFile) { message.warning('请选择文件'); return }
    setImporting(true); setImportResult(null)
    try {
      const res = await measurementApi.importFile(importFile)
      setImportResult(res.data)
      if (res.data.errors.length === 0) {
        message.success(`成功导入 ${res.data.success} 条`)
        setImportOpen(false); setImportFile(null); fetchData()
      }
    } catch { message.error('导入失败') } finally { setImporting(false) }
  }
  const downloadTemplate = async () => {
    try {
      const res = await measurementApi.downloadTemplate() as unknown as Blob
      const url = URL.createObjectURL(res)
      const a = document.createElement('a')
      a.href = url; a.download = 'measurements_template.xlsx'; a.click()
      URL.revokeObjectURL(url)
    } catch { message.error('模板下载失败') }
  }

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await measurementApi.list({ pageNo: p, pageSize, keyword: keyword || undefined, industry })
      setData(res.data.items); setTotal(res.data.total)
    } finally { setLoading(false) }
  }
  useEffect(() => { fetchData(1); setPage(1) }, [industry]) // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => { setEditing(null); form.resetFields(); setModalOpen(true) }
  const openEdit = (r: ServiceMeasurement) => {
    setEditing(r)
    form.setFieldsValue({ ...r, service_date: r.service_date ? dayjs(r.service_date) : undefined })
    if (r.customer_id && r.customer_name) customerSelect.setInitialOption({ label: r.customer_name, value: r.customer_id })
    setModalOpen(true)
  }
  const handleSubmit = async () => {
    let values
    try { values = await form.validateFields() } catch { return }
    const payload: Record<string, unknown> = { ...values, service_date: values.service_date ? values.service_date.format('YYYY-MM-DD') : undefined }
    if (values.customer_id) {
      const opt = customerSelect.options.find((o) => o.value === values.customer_id)
      if (opt) payload.customer_name = opt.label
    }
    try {
      if (editing) { await measurementApi.update(editing.id, payload); message.success('已更新') }
      else { await measurementApi.create(payload); message.success('已录入') }
      setModalOpen(false); fetchData()
    } catch { message.error('保存失败') }
  }
  const doDelete = (r: ServiceMeasurement) => Modal.confirm({
    title: '删除实测记录', content: `确认删除 ${r.record_no}？`, okType: 'danger',
    onOk: async () => { await measurementApi.remove(r.id); message.success('已删除'); fetchData() },
  })
  const openStats = async () => { setStatsOpen(true); try { setStats((await measurementApi.stats()).data || []) } catch { setStats([]) } }

  // 列顺序与导出/导入模板表头一致
  const columns: ColumnsType<ServiceMeasurement> = [
    { title: '记录号', dataIndex: 'record_no', width: 140, fixed: 'left', render: (v) => <span className="font-mono text-xs">{v}</span> },
    { title: '客户', dataIndex: 'customer_name', width: 160, ellipsis: true, render: (v) => v || '-' },
    { title: '服务日期', dataIndex: 'service_date', width: 110, render: (v) => v || '-' },
    { title: '行业', dataIndex: 'industry', width: 80, render: (v) => v ? <Tag>{v}</Tag> : '-' },
    { title: '设备名称', dataIndex: 'equipment_name', width: 120, ellipsis: true, render: (v) => v || '-' },
    { title: '设备型号', dataIndex: 'equipment_model', width: 110, render: (v) => v || '-' },
    { title: '物料', dataIndex: 'material_name', width: 100, render: (v) => v || '-' },
    { title: '筛分效率%', dataIndex: 'screen_efficiency', width: 100, align: 'right', render: num },
    { title: '处理量t/h', dataIndex: 'throughput_tph', width: 100, align: 'right', render: num },
    { title: '运行电流A', dataIndex: 'running_current_a', width: 100, align: 'right', render: num },
    { title: '振源温度℃', dataIndex: 'source_temp_c', width: 100, align: 'right', render: num },
    { title: '日运行h', dataIndex: 'daily_run_hours', width: 90, align: 'right', render: num },
    { title: '服务人员', dataIndex: 'engineer_name', width: 100, render: (v) => v || '-' },
    {
      title: '', key: 'actions', width: 110, fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          <a className="text-primary text-sm px-2" onClick={() => openEdit(r)}>编辑</a>
          <a className="text-rose-500 text-sm px-2" onClick={() => doDelete(r)}>删除</a>
        </Space>
      ),
    },
  ]

  const statColumns: ColumnsType<MeasurementModelStat> = [
    { title: '设备型号', dataIndex: 'equipment_model' },
    { title: '样本数', dataIndex: 'count', width: 80, align: 'right' },
    { title: '平均筛分效率%', dataIndex: 'avg_efficiency', width: 130, align: 'right', render: num },
    { title: '平均处理量t/h', dataIndex: 'avg_throughput', width: 130, align: 'right', render: num },
    { title: '平均电流A', dataIndex: 'avg_current', width: 110, align: 'right', render: num },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">售后实测数据</h1>
          <p className="text-sm text-slate-500 mt-0.5">现场设备运行实测台账，沉淀为设备运行数据库，支撑设备健康分析</p>
        </div>
        <Space>
          <Button icon={<BarChartOutlined />} onClick={openStats}>按机型统计</Button>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/measurements/export/excel', 'measurements.xlsx')}>导出</Button>
          <Button icon={<UploadOutlined />} onClick={() => { setImportFile(null); setImportResult(null); setImportOpen(true) }}>批量导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>录入实测</Button>
        </Space>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input placeholder="客户 / 设备型号 / 物料" prefix={<SearchOutlined className="text-slate-400" />} value={keyword}
            onChange={(e) => setKeyword(e.target.value)} onPressEnter={() => { setPage(1); fetchData(1) }} allowClear style={{ width: 240 }} />
          <Select placeholder="行业" allowClear style={{ width: 140 }} value={industry} onChange={setIndustry} options={INDUSTRY_OPTIONS} />
          <Button onClick={() => { setPage(1); fetchData(1) }}>筛选</Button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={data} loading={loading} scroll={{ x: 1500 }}
          pagination={{ current: page, total, pageSize, showTotal: (t) => `共 ${t} 条`, onChange: (p) => { setPage(p); fetchData(p) } }} />
      </div>

      <Modal title={editing ? '编辑实测数据' : '录入实测数据'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)}
        okText="保存" destroyOnClose width={720}>
        <Form form={form} layout="vertical" className="mt-4">
          <div className="grid grid-cols-3 gap-3">
            <Form.Item name="customer_id" label="客户">
              <Select showSearch filterOption={false} allowClear placeholder="搜索客户" options={customerSelect.options} loading={customerSelect.loading}
                onSearch={customerSelect.onSearch} onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
            </Form.Item>
            <Form.Item name="service_date" label="服务日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="industry" label="行业"><Select options={INDUSTRY_OPTIONS} allowClear /></Form.Item>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Form.Item name="equipment_name" label="设备名称"><Input /></Form.Item>
            <Form.Item name="equipment_model" label="设备型号"><Input placeholder="如：YA1530" /></Form.Item>
            <Form.Item name="product_no" label="产品编号"><Input /></Form.Item>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <Form.Item name="material_name" label="物料名称"><Input /></Form.Item>
            <Form.Item name="feed_size_mm" label="入料粒度mm"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="layer_thickness_mm" label="料层厚度mm"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="motor_power_kw" label="电机功率kW"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <Form.Item name="screen_efficiency" label="筛分效率%"><InputNumber min={0} max={100} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="throughput_tph" label="处理量t/h"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="running_current_a" label="运行电流A"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="daily_run_hours" label="日运行h"><InputNumber min={0} max={24} style={{ width: '100%' }} /></Form.Item>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <Form.Item name="source_temp_c" label="振源温度℃"><InputNumber style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="ambient_temp_c" label="环境温度℃"><InputNumber style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="service_rating" label="服务评价"><Select options={RATING} allowClear /></Form.Item>
            <Form.Item name="product_rating" label="产品评价"><Select options={PRODUCT_RATING} allowClear /></Form.Item>
          </div>
          <Form.Item name="result_desc" label="服务结果描述"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="issues" label="未解决问题"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="批量导入实测数据" open={importOpen} onOk={doImport} confirmLoading={importing}
        onCancel={() => { setImportOpen(false); setImportFile(null); setImportResult(null) }} okText="开始导入" cancelText="取消" width={560}>
        <div className="space-y-4 py-1">
          <div className="text-sm text-slate-500">
            支持 Excel(.xlsx) 或 CSV，第一行为表头。列名兼容中文（与导出/模板一致）：
            <div className="mt-2 bg-slate-50 rounded p-2 text-sm text-slate-700 break-all">
              记录号、客户、服务日期、行业、设备名称、设备型号、物料、筛分效率%、处理量t/h、运行电流A、振源温度、日运行h、服务人员
            </div>
            <div className="mt-1 text-sm text-slate-400">记录号留空将自动生成；客户名称为文本（如需关联客户主数据可在导入后编辑）。</div>
            <Button type="link" size="small" className="px-0 mt-1" icon={<DownloadOutlined />} onClick={downloadTemplate}>下载导入模板</Button>
          </div>
          <Upload.Dragger maxCount={1} accept=".xlsx,.xls,.csv" beforeUpload={(f) => { setImportFile(f as File); setImportResult(null); return false }}
            onRemove={() => setImportFile(null)} fileList={importFile ? [{ uid: '1', name: importFile.name } as any] : []}>
            <p className="text-slate-500"><UploadOutlined className="mr-1" />点击或拖拽文件到此处</p>
          </Upload.Dragger>
          {importResult && (
            <div className="space-y-2">
              <Alert type={importResult.errors.length === 0 ? 'success' : 'warning'} showIcon
                message={`导入完成：成功 ${importResult.success} 条，失败 ${importResult.failed} 条`} />
              {importResult.errors.length > 0 && (
                <div className="max-h-40 overflow-y-auto bg-red-50 rounded p-2">
                  {importResult.errors.map((e, i) => (
                    <div key={i} className="text-sm text-red-600">第 {e.row} 行：{e.reason}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>

      <Drawer title="按设备型号统计" open={statsOpen} onClose={() => setStatsOpen(false)} width={620}>
        <p className="text-sm text-slate-500 mb-3">基于实测样本聚合，反映各机型现场运行表现。</p>
        <Table rowKey="equipment_model" columns={statColumns} dataSource={stats} size="small" pagination={false} />
      </Drawer>
    </div>
  )
}
