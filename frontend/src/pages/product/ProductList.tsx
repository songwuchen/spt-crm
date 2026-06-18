import { useState, useEffect } from 'react'
import { Button, Table, Input, Select, Tag, Modal, Form, InputNumber, Space, Switch, message, Tabs } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined } from '@ant-design/icons'
import { productApi } from '@/api/product'
import { usePageTitle } from '@/hooks/usePageTitle'
import { quoteLineItemTypeLabels as itemTypeLabels } from '@/constants/labels'
import type { ColumnsType } from 'antd/es/table'
import ImportExcelModal from '@/components/ImportExcelModal'

interface ProductItem {
  id: string; product_code: string; name: string; category_id: string | null
  item_type: string | null; spec: string | null; unit: string | null
  unit_price: number | null; cost_price: number | null; leadtime_days: number | null
  is_active: boolean; remark: string | null; created_at: string
  usage_count?: number
}

interface Category {
  id: string; name: string; parent_id: string | null; sort_order: number; description: string | null
}

export default function ProductList() {
  usePageTitle('产品目录')
  const [items, setItems] = useState<ProductItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterType, setFilterType] = useState<string | undefined>()
  const [filterCat, setFilterCat] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)

  const [categories, setCategories] = useState<Category[]>([])
  const [productModal, setProductModal] = useState(false)
  const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null)
  const [form] = Form.useForm()

  const [importModal, setImportModal] = useState(false)
  const [catModal, setCatModal] = useState(false)
  const [editingCat, setEditingCat] = useState<Category | null>(null)
  const [catForm] = Form.useForm()

  const fetchProducts = async (p = page) => {
    setLoading(true)
    try {
      const res = await productApi.list({ pageNo: p, pageSize: 20, keyword: keyword || undefined, item_type: filterType, category_id: filterCat })
      setItems(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally { setLoading(false) }
  }

  const fetchCategories = async () => {
    try {
      const res = await productApi.listCategories()
      setCategories(res.data || [])
    } catch {
      message.error('加载分类失败')
    }
  }

  useEffect(() => { fetchCategories() }, [])
  useEffect(() => { fetchProducts(page) }, [page, filterType, filterCat])

  const handleSearch = () => { setPage(1); fetchProducts(1) }

  const catMap = Object.fromEntries(categories.map(c => [c.id, c.name]))

  // Build category tree for display
  const getCatPath = (catId: string | null): string => {
    if (!catId) return '-'
    const cat = categories.find(c => c.id === catId)
    if (!cat) return catMap[catId] || catId
    if (cat.parent_id) {
      const parent = categories.find(c => c.id === cat.parent_id)
      return parent ? `${parent.name} / ${cat.name}` : cat.name
    }
    return cat.name
  }

  const handleProductSubmit = async () => {
    const values = await form.validateFields()
    if (editingProduct) {
      await productApi.update(editingProduct.id, values)
      message.success('产品已更新')
    } else {
      await productApi.create(values)
      message.success('产品已创建')
    }
    setProductModal(false)
    form.resetFields()
    setEditingProduct(null)
    fetchProducts()
  }

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: '确认删除', content: '删除后无法恢复', okType: 'danger',
      onOk: async () => { await productApi.delete(id); message.success('已删除'); fetchProducts() },
    })
  }

  const handleCatSubmit = async () => {
    const values = await catForm.validateFields()
    if (editingCat) {
      await productApi.updateCategory(editingCat.id, values)
      message.success('分类已更新')
    } else {
      await productApi.createCategory(values)
      message.success('分类已创建')
    }
    setCatModal(false)
    catForm.resetFields()
    setEditingCat(null)
    fetchCategories()
  }

  const handleDeleteCat = (id: string) => {
    Modal.confirm({
      title: '确认删除分类', content: '分类下有产品时无法删除', okType: 'danger',
      onOk: async () => { await productApi.deleteCategory(id); message.success('已删除'); fetchCategories() },
    })
  }

  const columns: ColumnsType<ProductItem> = [
    { title: '编码', dataIndex: 'product_code', width: 120,
      render: (v) => <span className="font-mono text-sm font-bold text-primary">{v}</span> },
    { title: '名称', dataIndex: 'name', width: 200,
      render: (v) => <span className="font-semibold text-slate-800">{v}</span> },
    { title: '分类', dataIndex: 'category_id', width: 140,
      render: (v) => v ? <span className="text-sm text-slate-600">{getCatPath(v)}</span> : '-' },
    { title: '类型', dataIndex: 'item_type', width: 80,
      render: (v) => v ? <Tag color="blue">{itemTypeLabels[v] || v}</Tag> : '-' },
    { title: '规格', dataIndex: 'spec', width: 150, ellipsis: true },
    { title: '单位', dataIndex: 'unit', width: 60 },
    { title: '标准单价', dataIndex: 'unit_price', width: 110, align: 'right',
      render: (v) => v != null ? <span className="font-bold">¥{Number(v).toLocaleString()}</span> : '-' },
    { title: '成本价', dataIndex: 'cost_price', width: 100, align: 'right',
      render: (v) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
    { title: '交期(天)', dataIndex: 'leadtime_days', width: 80 },
    { title: '引用', dataIndex: 'usage_count', width: 60, align: 'center',
      render: (v) => v ? <span className="text-sm font-bold text-amber-600">{v}次</span> : <span className="text-slate-300">-</span> },
    { title: '状态', dataIndex: 'is_active', width: 70,
      render: (v) => v ? <Tag color="success">启用</Tag> : <Tag>停用</Tag> },
    { title: '', key: 'actions', width: 100,
      render: (_, r) => (
        <Space size={4}>
          <a className="text-primary text-sm font-bold" onClick={() => {
            setEditingProduct(r); form.setFieldsValue(r); setProductModal(true)
          }}><EditOutlined /></a>
          <a className="text-rose-500 text-sm font-bold" onClick={() => handleDelete(r.id)}><DeleteOutlined /></a>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-slate-900">产品目录</h1>
      </div>

      <Tabs defaultActiveKey="products" items={[
        {
          key: 'products',
          label: '产品列表',
          children: (
            <>
              <div className="flex items-center gap-3 mb-4 flex-wrap">
                <Input.Search placeholder="搜索编码/名称/规格" value={keyword} onChange={(e) => setKeyword(e.target.value)}
                  onSearch={handleSearch} enterButton style={{ width: 280 }} allowClear />
                <Select placeholder="类型" allowClear style={{ width: 120 }} value={filterType} onChange={setFilterType}
                  options={Object.entries(itemTypeLabels).map(([k, v]) => ({ label: v, value: k }))} />
                <Select placeholder="分类" allowClear style={{ width: 140 }} value={filterCat} onChange={setFilterCat}
                  options={categories.map(c => ({ label: c.name, value: c.id }))} />
                <div className="flex-1" />
                <Button icon={<UploadOutlined />} onClick={() => setImportModal(true)}>导入</Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => {
                  setEditingProduct(null); form.resetFields(); form.setFieldsValue({ is_active: true }); setProductModal(true)
                }}>新建产品</Button>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <Table rowKey="id" columns={columns} dataSource={items} loading={loading} size="small"
                  scroll={{ x: 1200 }}
                  pagination={{ current: page, total, pageSize: 20, onChange: setPage, showTotal: (t) => `共 ${t} 条` }} />
              </div>
            </>
          ),
        },
        {
          key: 'categories',
          label: '产品分类',
          children: (
            <>
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm text-slate-500">管理产品分类，便于产品组织和筛选</span>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => {
                  setEditingCat(null); catForm.resetFields(); setCatModal(true)
                }}>新建分类</Button>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <Table rowKey="id" dataSource={categories} size="small" pagination={false}
                  columns={[
                    { title: '分类名称', dataIndex: 'name', width: 200,
                      render: (v: string) => <span className="font-semibold text-slate-800">{v}</span> },
                    { title: '上级分类', dataIndex: 'parent_id', width: 140,
                      render: (v: string | null) => v ? <span className="text-sm text-slate-600">{catMap[v] || '-'}</span> : <span className="text-slate-300">顶级</span> },
                    { title: '描述', dataIndex: 'description', width: 300 },
                    { title: '排序', dataIndex: 'sort_order', width: 80 },
                    { title: '', key: 'actions', width: 100,
                      render: (_: unknown, r: Category) => (
                        <Space size={4}>
                          <a className="text-primary text-sm font-bold" onClick={() => {
                            setEditingCat(r); catForm.setFieldsValue(r); setCatModal(true)
                          }}><EditOutlined /></a>
                          <a className="text-rose-500 text-sm font-bold" onClick={() => handleDeleteCat(r.id)}><DeleteOutlined /></a>
                        </Space>
                      ),
                    },
                  ]}
                />
              </div>
            </>
          ),
        },
      ]} />

      {/* Product Modal */}
      <Modal title={editingProduct ? '编辑产品' : '新建产品'} open={productModal}
        onOk={handleProductSubmit} onCancel={() => { setProductModal(false); setEditingProduct(null); form.resetFields() }}
        width={650}>
        <Form form={form} layout="vertical">
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="product_code" label="产品编码" rules={[{ required: true, message: '请输入产品编码' }]}>
              <Input placeholder="如 P-001" />
            </Form.Item>
            <Form.Item name="name" label="产品名称" rules={[{ required: true, message: '请输入产品名称' }]}>
              <Input placeholder="请输入产品名称" />
            </Form.Item>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <Form.Item name="category_id" label="分类">
              <Select placeholder="请选择分类" allowClear
                options={categories.map(c => ({ label: c.name, value: c.id }))} />
            </Form.Item>
            <Form.Item name="item_type" label="类型">
              <Select placeholder="请选择类型" allowClear
                options={Object.entries(itemTypeLabels).map(([k, v]) => ({ label: v, value: k }))} />
            </Form.Item>
            <Form.Item name="unit" label="单位">
              <Input placeholder="台/套/件" />
            </Form.Item>
          </div>
          <Form.Item name="spec" label="规格">
            <Input placeholder="规格描述" />
          </Form.Item>
          <div className="grid grid-cols-3 gap-4">
            <Form.Item name="unit_price" label="标准单价">
              <InputNumber className="w-full" min={0} precision={2} placeholder="0.00" />
            </Form.Item>
            <Form.Item name="cost_price" label="成本价">
              <InputNumber className="w-full" min={0} precision={2} placeholder="0.00" />
            </Form.Item>
            <Form.Item name="leadtime_days" label="交期(天)">
              <InputNumber className="w-full" min={0} placeholder="0" />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="is_active" label="状态" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
          </div>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} placeholder="产品备注" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Category Modal */}
      <Modal title={editingCat ? '编辑分类' : '新建分类'} open={catModal}
        onOk={handleCatSubmit} onCancel={() => { setCatModal(false); setEditingCat(null); catForm.resetFields() }}>
        <Form form={catForm} layout="vertical">
          <Form.Item name="name" label="分类名称" rules={[{ required: true, message: '请输入分类名称' }]}>
            <Input placeholder="请输入分类名称" />
          </Form.Item>
          <Form.Item name="parent_id" label="上级分类">
            <Select placeholder="无（顶级分类）" allowClear
              options={categories.filter(c => c.id !== editingCat?.id).map(c => ({ label: c.name, value: c.id }))} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="分类描述" />
          </Form.Item>
          <Form.Item name="sort_order" label="排序">
            <InputNumber className="w-full" min={0} placeholder="0" />
          </Form.Item>
        </Form>
      </Modal>

      <ImportExcelModal
        open={importModal}
        onClose={() => setImportModal(false)}
        onSuccess={() => fetchProducts()}
        apiUrl="/api/v1/products/import/excel"
        title="导入产品"
        templateColumns={['产品编码', '名称', '类型', '规格', '单位', '单价', '成本价', '交期(天)']}
        templateUrl="/api/v1/products/import/template"
      />
    </div>
  )
}
