import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Select, Tag, Space, message, Tabs } from 'antd'
import { PlusOutlined, SearchOutlined, DeleteOutlined, FileTextOutlined } from '@ant-design/icons'
import { aiApi } from '@/api/ai'
import type { KnowledgeDoc, KnowledgeSearchResult } from '@/api/ai'
import { usePageTitle } from '@/hooks/usePageTitle'
import { t } from '@/locales'
import AttachmentPanel from '@/components/AttachmentPanel'

const { TextArea } = Input

const docTypeOptions = [
  { value: 'faq', label: 'FAQ / 常见问题' },
  { value: 'product', label: '产品知识' },
  { value: 'process', label: '流程规范' },
  { value: 'policy', label: '政策制度' },
  { value: 'manual', label: '操作手册' },
  { value: 'other', label: '其他' },
]

const docTypeColors: Record<string, string> = {
  faq: 'blue', product: 'green', process: 'orange', policy: 'purple', manual: 'cyan', other: 'default',
}

export default function KnowledgeBasePage() {
  usePageTitle('知识库')
  const [docs, setDocs] = useState<KnowledgeDoc[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [docType, setDocType] = useState<string | undefined>()

  // Create/Edit modal
  const [editModal, setEditModal] = useState(false)
  const [editingDoc, setEditingDoc] = useState<KnowledgeDoc | null>(null)
  const [form] = Form.useForm()

  // Search tab
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([])
  const [searching, setSearching] = useState(false)

  // Detail modal
  const [detailModal, setDetailModal] = useState(false)
  const [detailDoc, setDetailDoc] = useState<(KnowledgeDoc & { content_text: string }) | null>(null)

  const fetchDocs = async (page = pageNo) => {
    setLoading(true)
    try {
      const res = await aiApi.listKnowledgeDocs({ pageNo: page, pageSize: 20, keyword: keyword || undefined, doc_type: docType })
      setDocs(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchDocs() }, [])

  const handleCreate = () => {
    setEditingDoc(null)
    form.resetFields()
    form.setFieldsValue({ doc_type: 'other' })
    setEditModal(true)
  }

  const handleEdit = async (doc: KnowledgeDoc) => {
    try {
      const res = await aiApi.getKnowledgeDoc(doc.id)
      setEditingDoc(doc)
      form.setFieldsValue({
        title: res.data.title,
        doc_type: res.data.doc_type,
        content_text: res.data.content_text,
      })
      setEditModal(true)
    } catch {
      message.error('获取文档详情失败')
    }
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    try {
      if (editingDoc) {
        await aiApi.updateKnowledgeDoc(editingDoc.id, values)
        message.success('文档已更新')
      } else {
        await aiApi.createKnowledgeDoc(values)
        message.success('文档已创建')
      }
      setEditModal(false)
      fetchDocs()
    } catch {
      message.error('保存失败')
    }
  }

  const handleDelete = (doc: KnowledgeDoc) => {
    Modal.confirm({
      title: t('common.confirmDelete'),
      content: `确定要删除文档「${doc.title}」？`,
      okType: 'danger',
      onOk: async () => {
        await aiApi.deleteKnowledgeDoc(doc.id)
        message.success(t('common.deleted'))
        fetchDocs()
      },
    })
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await aiApi.searchKnowledge({ query: searchQuery, top_k: 10, doc_type: docType })
      setSearchResults(res.data)
    } catch {
      message.error('检索失败')
    } finally {
      setSearching(false)
    }
  }

  const handleViewDetail = async (docId: string) => {
    try {
      const res = await aiApi.getKnowledgeDoc(docId)
      setDetailDoc(res.data)
      setDetailModal(true)
    } catch {
      message.error('获取文档详情失败')
    }
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">AI 知识库</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理 RAG 知识文档，为 AI 分析提供上下文</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}
          className="shadow-lg shadow-primary/20 font-bold">
          添加文档
        </Button>
      </div>

      <Tabs items={[
        {
          key: 'docs',
          label: '文档管理',
          children: (
            <>
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
                <div className="flex gap-3 flex-wrap items-center">
                  <Input placeholder="搜索文档标题..." prefix={<SearchOutlined className="text-slate-400" />}
                    value={keyword} onChange={(e) => setKeyword(e.target.value)}
                    onPressEnter={() => { setPageNo(1); fetchDocs(1) }}
                    allowClear style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }} />
                  <Select placeholder="文档类型" allowClear style={{ width: 140 }} value={docType}
                    onChange={(v) => { setDocType(v); setPageNo(1); fetchDocs(1) }}
                    options={docTypeOptions} />
                  <Button onClick={() => { setPageNo(1); fetchDocs(1) }}>{t('common.filter')}</Button>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <Table rowKey="id" dataSource={docs} loading={loading} size="small"
                  pagination={{
                    current: pageNo, total, pageSize: 20,
                    showTotal: (t) => `共 ${t} 条`,
                    onChange: (p) => { setPageNo(p); fetchDocs(p) },
                  }}
                  columns={[
                    {
                      title: '文档', key: 'title', width: 300,
                      render: (_, r) => (
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
                            <FileTextOutlined className="text-indigo-400" />
                          </div>
                          <div>
                            <a onClick={() => handleViewDetail(r.id)} className="text-sm font-bold text-slate-900 hover:text-primary">{r.title}</a>
                            <div className="text-[11px] text-slate-400">
                              {r.chunk_count} 个片段 {r.source_filename && `· ${r.source_filename}`}
                            </div>
                          </div>
                        </div>
                      ),
                    },
                    {
                      title: '类型', dataIndex: 'doc_type', width: 120,
                      render: (v: string) => <Tag color={docTypeColors[v] || 'default'}>{docTypeOptions.find(o => o.value === v)?.label || v}</Tag>,
                    },
                    {
                      title: '状态', dataIndex: 'status', width: 80,
                      render: (v: string) => <Tag color={v === 'active' ? 'success' : 'default'}>{v === 'active' ? '启用' : '归档'}</Tag>,
                    },
                    {
                      title: '创建人', dataIndex: 'created_by_name', width: 100,
                      render: (v) => v || <span className="text-slate-300">-</span>,
                    },
                    {
                      title: '创建时间', dataIndex: 'created_at', width: 120,
                      render: (v: string) => v ? <span className="text-sm text-slate-500">{new Date(v).toLocaleDateString('zh-CN')}</span> : '-',
                    },
                    {
                      title: '', key: 'actions', width: 140, fixed: 'right',
                      render: (_, r) => (
                        <Space size={0}>
                          <a onClick={() => handleViewDetail(r.id)} className="text-primary text-sm font-bold uppercase tracking-widest px-2">{t('common.detail')}</a>
                          <a onClick={() => handleEdit(r)} className="text-slate-500 text-sm font-bold uppercase tracking-widest px-2 hover:text-primary">{t('common.edit')}</a>
                          <a onClick={() => handleDelete(r)} className="text-sm font-bold uppercase tracking-widest px-2 text-rose-500 hover:text-rose-600">{t('common.delete')}</a>
                        </Space>
                      ),
                    },
                  ]}
                />
              </div>
            </>
          ),
        },
        {
          key: 'search',
          label: 'RAG 检索',
          children: (
            <div>
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
                <h3 className="text-sm font-bold text-slate-900 mb-3">知识检索</h3>
                <div className="flex gap-3 items-start">
                  <TextArea placeholder="输入查询内容，从知识库中检索相关片段..."
                    value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                    autoSize={{ minRows: 2, maxRows: 4 }} className="flex-1" />
                  <Button type="primary" icon={<SearchOutlined />} loading={searching}
                    onClick={handleSearch} className="mt-1">
                    检索
                  </Button>
                </div>
              </div>

              {searchResults.length > 0 && (
                <div className="space-y-3">
                  {searchResults.map((r, i) => (
                    <div key={r.chunk_id} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-400">#{i + 1}</span>
                          <a onClick={() => handleViewDetail(r.document_id)} className="text-sm font-bold text-primary hover:underline">{r.doc_title}</a>
                          <span className="text-[11px] text-slate-400">片段 {r.chunk_index + 1}</span>
                        </div>
                        <Tag color="blue">相关度 {r.score}</Tag>
                      </div>
                      <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{r.content}</p>
                    </div>
                  ))}
                </div>
              )}

              {searchResults.length === 0 && searchQuery && !searching && (
                <div className="text-center py-12 text-slate-400">
                  未找到相关知识片段
                </div>
              )}
            </div>
          ),
        },
      ]} />

      {/* Create/Edit Modal */}
      <Modal
        title={editingDoc ? '编辑文档' : '添加知识文档'}
        open={editModal}
        onOk={handleSave}
        onCancel={() => setEditModal(false)}
        width={700}
        okText={t('common.save')}
      >
        <Form form={form} layout="vertical" className="py-2">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="文档标题" />
          </Form.Item>
          <Form.Item name="doc_type" label="类型" rules={[{ required: true }]}>
            <Select options={docTypeOptions} />
          </Form.Item>
          <Form.Item name="content_text" label="内容" rules={[{ required: true, message: '请输入文档内容' }]}>
            <TextArea autoSize={{ minRows: 8, maxRows: 20 }} placeholder="输入文档内容，系统会自动分段用于 RAG 检索..." />
          </Form.Item>
        </Form>
        {editingDoc ? (
          <div className="border-t border-slate-100 pt-3">
            <div className="text-sm font-bold text-slate-700 mb-2">附件</div>
            <AttachmentPanel bizType="knowledge_doc" bizId={editingDoc.id} />
          </div>
        ) : (
          <div className="text-xs text-slate-400 border-t border-slate-100 pt-3">保存文档后可上传附件</div>
        )}
      </Modal>

      {/* Detail Modal */}
      <Modal
        title={detailDoc?.title || '文档详情'}
        open={detailModal}
        onCancel={() => setDetailModal(false)}
        footer={null}
        width={700}
      >
        {detailDoc && (
          <div className="py-2">
            <div className="flex gap-3 mb-4">
              <Tag color={docTypeColors[detailDoc.doc_type] || 'default'}>
                {docTypeOptions.find(o => o.value === detailDoc.doc_type)?.label || detailDoc.doc_type}
              </Tag>
              <span className="text-sm text-slate-500">{detailDoc.chunk_count} 个片段</span>
              <span className="text-sm text-slate-400">创建于 {new Date(detailDoc.created_at).toLocaleDateString('zh-CN')}</span>
            </div>
            <div className="bg-slate-50 rounded-lg p-4 max-h-96 overflow-y-auto">
              <pre className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{detailDoc.content_text}</pre>
            </div>
            <div className="mt-4">
              <div className="text-sm font-bold text-slate-700 mb-2">附件</div>
              <AttachmentPanel bizType="knowledge_doc" bizId={detailDoc.id} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
