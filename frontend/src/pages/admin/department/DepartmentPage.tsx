import { useState, useEffect } from 'react'
import { Tree, Button, Modal, Form, Input, InputNumber, message, Space } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { departmentApi } from '@/api/department'
import type { Department } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'

function toTreeData(departments: Department[]): any[] {
  return departments.map((d) => ({
    key: d.id,
    title: (
      <span className="text-sm font-medium text-slate-700">{d.name}</span>
    ),
    data: d,
    children: d.children?.length ? toTreeData(d.children) : [],
  }))
}

export default function DepartmentPage() {
  usePageTitle('部门管理')
  const [tree, setTree] = useState<Department[]>([])
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState<Department | null>(null)
  const [parentId, setParentId] = useState<string | undefined>()
  const [selectedDept, setSelectedDept] = useState<Department | null>(null)
  const [form] = Form.useForm()

  const fetchTree = async () => {
    const res = await departmentApi.tree()
    setTree(res.data)
  }

  useEffect(() => { fetchTree() }, [])

  const openCreate = (pId?: string) => {
    setEditing(null)
    setParentId(pId)
    form.resetFields()
    setModal(true)
  }

  const openEdit = (dept: Department) => {
    setEditing(dept)
    setParentId(dept.parent_id || undefined)
    form.setFieldsValue({ name: dept.name, sort_order: dept.sort_order })
    setModal(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    if (editing) {
      await departmentApi.update(editing.id, values)
      message.success('部门已更新')
    } else {
      await departmentApi.create({ ...values, parent_id: parentId })
      message.success('部门已创建')
    }
    setModal(false)
    fetchTree()
  }

  const handleDelete = (dept: Department) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除部门「${dept.name}」？`,
      okType: 'danger',
      onOk: async () => {
        await departmentApi.delete(dept.id)
        message.success('部门已删除')
        setSelectedDept(null)
        fetchTree()
      },
    })
  }

  const countNodes = (depts: Department[]): number =>
    depts.reduce((acc, d) => acc + 1 + (d.children ? countNodes(d.children) : 0), 0)

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">部门管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理组织架构和部门层级</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />}
          onClick={() => openCreate()}
          className="shadow-lg shadow-primary/20 font-bold">
          新建顶级部门
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Department Tree */}
        <div className="col-span-5">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">account_tree</span>
                <h3 className="text-sm font-bold text-slate-900">组织架构</h3>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-bold">
                {countNodes(tree)} 个部门
              </span>
            </div>
            <div className="p-4">
              {tree.length > 0 ? (
                <Tree
                  treeData={toTreeData(tree)}
                  defaultExpandAll
                  showIcon
                  blockNode
                  onSelect={(_, info) => {
                    setSelectedDept((info.node as any).data)
                  }}
                  selectedKeys={selectedDept ? [selectedDept.id] : []}
                  className="[&_.ant-tree-node-content-wrapper]:rounded-lg [&_.ant-tree-node-selected]:!bg-primary/5"
                />
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <span className="material-symbols-outlined text-4xl text-slate-200 mb-3">account_tree</span>
                  <p className="text-sm text-slate-400">暂无部门数据</p>
                  <p className="text-xs text-slate-300 mt-1">点击上方按钮创建第一个部门</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Department Detail */}
        <div className="col-span-7">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
              <span className="material-symbols-outlined text-slate-400">info</span>
              <h3 className="text-sm font-bold text-slate-900">
                {selectedDept ? selectedDept.name : '部门详情'}
              </h3>
            </div>

            {selectedDept ? (
              <div className="p-5">
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">部门名称</div>
                    <div className="text-sm font-semibold text-slate-700">{selectedDept.name}</div>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">排序权重</div>
                    <div className="text-sm font-semibold text-slate-700">{selectedDept.sort_order}</div>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 col-span-2">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">物化路径</div>
                    <div className="text-sm font-mono text-slate-500">{selectedDept.path}</div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <Button onClick={() => openCreate(selectedDept.id)}>
                    <span className="material-symbols-outlined text-sm mr-1">add</span>
                    添加子部门
                  </Button>
                  <Button onClick={() => openEdit(selectedDept)}>
                    <span className="material-symbols-outlined text-sm mr-1">edit</span>
                    编辑
                  </Button>
                  <Button danger onClick={() => handleDelete(selectedDept)}>
                    <span className="material-symbols-outlined text-sm mr-1">delete</span>
                    删除
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <span className="material-symbols-outlined text-5xl text-slate-200 mb-3">touch_app</span>
                <p className="text-sm text-slate-400">请从左侧选择部门</p>
                <p className="text-xs text-slate-300 mt-1">选择部门后可查看详情和管理操作</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal title={editing ? '编辑部门' : '新建部门'} open={modal} onOk={handleSubmit} onCancel={() => setModal(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="部门名称" rules={[{ required: true }]}>
            <Input placeholder="请输入部门名称" />
          </Form.Item>
          <Form.Item name="sort_order" label="排序权重" initialValue={0}>
            <InputNumber min={0} className="w-full" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
