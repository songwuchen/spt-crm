/**
 * 本地试打：PDF 预览弹层 + 安装图/领用单版式。
 * 路由：/dev/drawing-print-demo（无需登录）
 */
import { useState } from 'react'
import { Button, Space, Typography, message } from 'antd'
import {
  buildCsDrawingPrintDocument,
  buildInstallPrintDocument,
  buildRequisitionPrintDocument,
} from '@/pages/drawing/schemePrint'
import { htmlToPdfBlob, DRAWING_PRINT_MARGINS } from '@/utils/htmlToPdf'
import { openPdfPreview, setPdfPreviewLoading, closePdfPreview } from '@/components/PdfPreviewModal'
import type { FieldDefinition, WfFlowStep } from '@/types/lowcode'

const { Title, Paragraph } = Typography

const DEMO_STEPS: WfFlowStep[] = [
  {
    node_instance_id: 's3', node_name: '总工审批', status: 'completed', status_text: '已完成',
    action: 'approve', opinion: '同意',
    handler_name: '曹修国', completed_at: '2026-08-15T14:04:00',
  },
  {
    node_instance_id: 's2', node_name: '市场支持中心', status: 'completed', status_text: '已完成',
    action: 'approve', opinion: '同意',
    handler_name: '王亚飞', completed_at: '2026-08-15T11:26:00',
  },
  {
    node_instance_id: 's1', node_name: '部门审批', status: 'completed', status_text: '已完成',
    action: 'approve', opinion: '同意',
    handler_name: '张贺', completed_at: '2026-08-15T10:31:00',
  },
  {
    node_instance_id: 'start', node_name: '流程发起', node_type: 'start',
    status: 'completed', status_text: '已完成', action: 'submit',
    handler_name: '尚高华', completed_at: '2026-08-15T09:00:00',
  },
]

const INSTALL_FIELDS: FieldDefinition[] = [
  {
    id: 'is_new_project', type: 'radio', label: '是否为新项目',
    options: [{ label: '是', value: '是' }, { label: '否', value: '否' }],
  },
  {
    id: 'drawing_issue_type', type: 'radio', label: '下图类型',
    options: [
      { label: '出方案图', value: '出方案图' },
      { label: '出测绘图', value: '出测绘图' },
    ],
  },
  {
    id: 'pickup_purpose', type: 'radio', label: '领图目的',
    options: [
      { label: '技术交流', value: '技术交流' },
      { label: '投标', value: '投标' },
    ],
  },
  {
    id: 'install_method', type: 'radio', label: '安装方式',
    options: [{ label: '固定坐式', value: '固定坐式' }],
  },
  {
    id: 'install_position', type: 'radio', label: '安装位置',
    options: [{ label: '室内', value: '室内' }],
  },
]

const INSTALL_FORM: Record<string, unknown> = {
  serial_no: '202608154176',
  project_no: 'PRJ202608005',
  order_person: { real_name: '孙家兴' },
  department: 'dept_yj',
  applicant: { real_name: '尚高华' },
  card_date: '2026-08-15',
  design_card_no: '02-2026081501',
  is_new_project: '是',
  drawing_issue_type: '出方案图',
  pickup_purpose: '技术交流',
  apply_or_change: '武钢资源集团鄂州球团有限公司煤粉密闭振动筛',
  attachment_names: '冶金矿山部孙家兴8.15—煤粉密闭振动筛技术规格书',
  install_method: '固定坐式',
  install_position: '室内',
  product_model: '/',
  scheme_detail: [{
    equipment_name: '煤粉密闭振动筛2台',
    design_req: '单台处理能力≥25 (每24小时连续运行，330天/年工作) t/h/台',
    need_pricing: '是',
  }],
  scheme_material: [{
    industry: '其他',
    material_name: '煤粉',
    mesh_size: '/',
    throughput: '/',
    feed_size: '/',
    bulk_density: '/',
    need_screening_eff: '否',
  }],
  install_env: [{ process_position: '/' }],
}

const INSTALL_LABELS = {
  depts: { dept_yj: '冶金矿山装备销售事业部' },
  users: {},
  projects: { PRJ202608005: 'PRJ202608005' },
  contracts: {},
}

export default function DrawingPrintDemoPage() {
  const [busy, setBusy] = useState(false)

  const openPreview = async (kind: 'install' | 'requisition' | 'cs') => {
    setBusy(true)
    const fileStem = kind === 'install'
      ? 'PRJ202608005-02-2026081501孙家兴'
      : kind === 'cs'
        ? 'WMGF202404162刘伟客户服务部2026-08-17'
        : 'WMGF202507027肖海华合同资料领用2026-08-13'
    setPdfPreviewLoading(true, fileStem)
    try {
      const html = kind === 'install'
        ? buildInstallPrintDocument({
          formData: INSTALL_FORM,
          fieldDefinitions: INSTALL_FIELDS,
          businessNo: '202608154176',
          flowSteps: DEMO_STEPS,
          labels: INSTALL_LABELS,
        })
        : kind === 'cs'
          ? buildCsDrawingPrintDocument({
            formData: {
              serial_no: '2026081703',
              order_person: { real_name: '刘伟' },
              applicant: { real_name: '付加婧' },
              department: 'dept_cs',
              apply_datetime: '2026-08-17',
              contract_no: 'WMGF202404162',
              drawing_no_note: '01KF03',
              transfer_channel: '下生产',
              attachment_name: '客服部 刘伟20260817-1',
              apply_reason_2:
                '1、激振器密封圈毡条 高幅筛 GFS-X-800-10配 2米；2、软连接 6片。请出图。',
            },
            fieldDefinitions: [
              {
                id: 'transfer_channel', type: 'radio', label: '图纸传递途径',
                options: [{ label: '下生产', value: '下生产' }],
              },
            ],
            businessNo: '2026081703',
            flowSteps: DEMO_STEPS,
            labels: {
              depts: { dept_cs: '客户服务部' },
              users: {},
              projects: {},
              contracts: {},
            },
          })
          : buildRequisitionPrintDocument({
            formData: {
              serial_no: '2026081301',
              order_person: { real_name: '肖海华' },
              applicant: { real_name: '肖海华' },
              department: 'dept_xunhan',
              apply_datetime: '2026-08-13',
              drawing_no: 'WMGF202507027',
              contract_no: 'WMGF202507027',
              transfer_channel: '邮箱',
              attachment_name: '无',
              apply_reason: '客户需要正式图纸资料',
            },
            fieldDefinitions: [],
            flowSteps: DEMO_STEPS,
            labels: { depts: { dept_xunhan: '迅焊业务部' }, users: {}, projects: {}, contracts: {} },
          })
      const { blob, fileName } = await htmlToPdfBlob(html, {
        orientation: 'landscape',
        fileName: fileStem,
        margins: DRAWING_PRINT_MARGINS,
      })
      openPdfPreview(blob, fileName)
    } catch (e) {
      closePdfPreview()
      message.error(e instanceof Error ? e.message : '生成 PDF 失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#f5f5f5',
      padding: 24,
    }}>
      <div style={{
        maxWidth: 560,
        background: '#fff',
        borderRadius: 12,
        padding: 28,
        boxShadow: '0 4px 24px rgba(0,0,0,.08)',
      }}>
        <Title level={4} style={{ marginTop: 0 }}>打印预览 · 试打</Title>
        <Paragraph type="secondary">
          对齐客户 Word 模板。安装图 / 合同图纸领用 / 客服领图均可预览。
        </Paragraph>
        <Space wrap>
          <Button type="primary" loading={busy} onClick={() => openPreview('install')}>
            预览安装图通知单
          </Button>
          <Button loading={busy} onClick={() => openPreview('requisition')}>
            预览合同图纸领用
          </Button>
          <Button loading={busy} onClick={() => openPreview('cs')}>
            预览客服领图
          </Button>
        </Space>
      </div>
    </div>
  )
}
