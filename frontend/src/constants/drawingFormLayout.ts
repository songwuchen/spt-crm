// 图纸 / 方案 / 生产卡 / 开票 / 收款：分区布局 + 栅格 span（对齐简道云 lineWidth，×2 为 antd Col span）
import type { FieldDefinition } from '@/types/lowcode'

export type DrawingSection = { title: string; fieldIds: string[] }

export type DrawingFormLayoutSpec = {
  sections: DrawingSection[]
  /** fieldId -> antd Col span (default 12 for short, 24 for long) */
  spans?: Record<string, number>
  contentMaxWidth?: number
  /**
   * 列表展开的明细表字段 id（简道云式主表 rowSpan + 明细多列）。
   * 也可用字段 props.list_expand=true 声明；二者任一即可。
   */
  listExpandDetail?: string
  /**
   * 多明细同时展开（如「主要产品信息」+「有其它排产产品明细」）。
   * 优先于 listExpandDetail；行高取各明细行数的最大值。
   */
  listExpandDetails?: string[]
  /**
   * 列表默认展示列（字段 id，顺序即列序）。对齐简道云「数据管理」扫视列；
   * 未配置时列表页走启发式。流水号列由列表页单独置顶，此处可省略 serial_no。
   */
  listColumns?: string[]
  /** 列表列宽（px）；未配则走列表页默认 */
  listColumnWidths?: Record<string, number>
  /** 列表列标题覆盖（如 project_no →「项目号」） */
  listColumnLabels?: Record<string, string>
  /**
   * 列表单元格不截断省略号，横向滚动看全（对齐简道云数据管理）。
   */
  listFullText?: boolean
  /** 明细子列展示上限（默认 8；产品明细可调高） */
  listDetailMaxCols?: number
}

export const DRAWING_FORM_LAYOUT: Record<string, DrawingFormLayoutSpec> = {
  drawing_requisition: {
    contentMaxWidth: 1080,
    // 对齐简道云数据管理列序（已去掉订货人/设计人文本、是否解密*）
    listColumns: [
      'apply_datetime', 'department', 'applicant', 'involve_std_drawing',
      'order_person', 'contract_no', 'apply_reason',
      'designer', 'product_model', 'transfer_channel', 'need_decrypt',
      'drawing_type', 'attachment_name', 'attachments', 'images',
      'design_dispatch', 'transfer_packaging_users', 'design_assignees',
      'offices', 'order_date', 'need_gm_approval',
    ],
    listFullText: true,
    listColumnWidths: {
      apply_datetime: 118,
      department: 200,
      applicant: 88,
      involve_std_drawing: 130,
      order_person: 88,
      contract_no: 240,
      apply_reason: 240,
      designer: 88,
      product_model: 120,
      transfer_channel: 120,
      need_decrypt: 96,
      drawing_type: 110,
      attachment_name: 220,
      attachments: 120,
      images: 120,
      design_dispatch: 100,
      transfer_packaging_users: 140,
      design_assignees: 160,
      offices: 200,
      order_date: 118,
      need_gm_approval: 150,
    },
    sections: [
      {
        title: '基本信息（创建时填写）',
        fieldIds: [
          'serial_no', 'apply_datetime', 'department', 'applicant', 'involve_std_drawing',
          'order_person', 'contract_no', 'apply_reason',
          'designer', 'product_model',
        ],
      },
      {
        title: '图纸传递与解密（创建时填写）',
        fieldIds: ['transfer_channel', 'need_decrypt', 'paper_print_tip'],
      },
      {
        title: '图纸与附件（创建时填写）',
        fieldIds: ['drawing_type', 'attachment_name', 'attachments', 'images'],
      },
      {
        title: '设计分派（审批时填写）',
        fieldIds: [
          'design_dispatch', 'transfer_packaging_users', 'design_assignees',
          'offices', 'order_date', 'need_gm_approval',
        ],
      },
    ],
    // span = 简道云 lineWidth × 2
    spans: {
      serial_no: 6, apply_datetime: 6, department: 6, applicant: 6, involve_std_drawing: 6,
      order_person: 6, contract_no: 6,
      apply_reason: 24,
      designer: 6, product_model: 12,
      transfer_channel: 8, need_decrypt: 8, paper_print_tip: 24,
      drawing_type: 8, attachment_name: 24, attachments: 12, images: 12,
      design_dispatch: 6, transfer_packaging_users: 6, design_assignees: 6,
      offices: 6, order_date: 12, need_gm_approval: 12,
    },
  },
  install_drawing_notice: {
    contentMaxWidth: 1100,
    // 对齐简道云数据管理扫视列；加宽 + 全文横向滚，避免公司名/事项被截成 …
    listColumns: [
      'apply_datetime', 'is_new_project', 'project_no', 'sales_person',
      'customer_name', 'matter', 'department', 'applicant', 'order_person',
      'dept_code', 'design_card_no', 'drawing_issue_type',
    ],
    listFullText: true,
    listColumnLabels: {
      project_no: '项目号',
      design_card_no: '设计卡号',
    },
    listColumnWidths: {
      apply_datetime: 118,
      is_new_project: 110,
      project_no: 160,
      sales_person: 96,
      customer_name: 280,
      matter: 280,
      department: 220,
      applicant: 96,
      order_person: 96,
      dept_code: 88,
      design_card_no: 150,
      drawing_issue_type: 120,
    },
    // 分区对齐简道云 separator + 发起/审批 optAuth（创建隐藏审批段标题）
    sections: [
      {
        title: '基本信息（创建时填写）',
        fieldIds: [
          'serial_no', 'apply_datetime', 'is_new_project', 'project_no',
          'sales_person', 'customer_name', 'matter',
          'applicant', 'department', 'order_person',
          'dept_code', 'is_xiaomeng', 'design_card_no',
        ],
      },
      {
        title: '图纸领取信息（创建时填写）',
        fieldIds: [
          'drawing_issue_type', 'drawing_types', 'need_decrypt', 'pickup_purpose',
          'apply_or_change', 'apply_reason_star',
        ],
      },
      {
        title: '安装图通知单及设计卡（创建时填写）',
        fieldIds: [
          'card_date', 'pre_designers', 'require_draw_date', 'product_model',
          'pre_designer_text',
          'scheme_detail', 'install_env',
          'install_position', 'foundation_drawing', 'install_method',
          'scheme_material', 'non_scheme_material',
          'attention', 'attachment_names', 'attachments_no_image', 'images',
        ],
      },
      {
        title: '业务反馈（审批时填写）',
        fieldIds: ['biz_feedback', 'lose_bid_reason'],
      },
      {
        title: '设计分派（审批时填写）',
        fieldIds: [
          'design_dispatch', 'transfer_packaging_users', 'design_assignees',
          'need_submit_drawing', 'offices_multi', 'order_date', 'transfer_sw_lwt',
        ],
      },
      {
        title: '打分信息（审批时填写）',
        fieldIds: [
          'score_attitude', 'score_progress', 'score_skill',
          'remark', 'score_total', 'score_date',
        ],
      },
    ],
    // span = 简道云 lineWidth × 2
    spans: {
      serial_no: 6, apply_datetime: 6, is_new_project: 12, project_no: 12,
      sales_person: 12, customer_name: 12, matter: 12,
      applicant: 6, department: 6, order_person: 6,
      dept_code: 6, is_xiaomeng: 6, design_card_no: 6,
      drawing_issue_type: 12, drawing_types: 24, need_decrypt: 6, pickup_purpose: 16,
      apply_or_change: 24, apply_reason_star: 24,
      biz_feedback: 12, lose_bid_reason: 12,
      card_date: 6, pre_designers: 6, require_draw_date: 6, product_model: 6,
      pre_designer_text: 6,
      scheme_detail: 24, install_env: 24, change_scheme: 24,
      scheme_material: 24, non_scheme_material: 24,
      install_position: 8, foundation_drawing: 8, install_method: 8,
      attention: 24, attachment_names: 24,
      attachments_no_image: 8, images: 8,
      design_dispatch: 12, transfer_packaging_users: 6, design_assignees: 6,
      need_submit_drawing: 12, offices_multi: 12, order_date: 8, transfer_sw_lwt: 8,
      score_attitude: 12, score_progress: 12, score_skill: 12,
      remark: 12, score_total: 12, score_date: 12,
    },
  },
  // 方案管理：scheme_type 分流；独有字段靠规则显隐，布局按类型分区列出
  scheme_management: {
    contentMaxWidth: 1100,
    listColumns: [
      'scheme_type', 'related_customer', 'related_project', 'contract_no',
      'customer_name', 'matter', 'apply_datetime',
      'department', 'applicant', 'order_person', 'product_model', 'design_card_no',
    ],
    listFullText: true,
    listColumnWidths: {
      scheme_type: 140,
      related_customer: 220,
      related_project: 220,
      contract_no: 220,
      customer_name: 280,
      matter: 280,
      apply_datetime: 118,
      department: 220,
      applicant: 96,
      order_person: 96,
      product_model: 140,
      design_card_no: 150,
    },
    sections: [
      {
        title: '方案类型',
        fieldIds: ['scheme_type', 'related_project', 'related_customer'],
      },
      {
        title: '共用基本信息',
        fieldIds: [
          'serial_no', 'apply_datetime', 'department', 'applicant', 'order_person',
          'apply_or_change',
          'product_model', 'design_dispatch', 'transfer_packaging_users',
          'design_assignees', 'order_date', 'images',
          // 有/无合同号总工都要填：只挂一次，避免两区各渲染一遍
          'need_gm_approval',
        ],
      },
      {
        title: '有合同号 · 领用',
        fieldIds: [
          'involve_std_drawing', 'contract_no', 'apply_reason', 'designer',
          'transfer_channel', 'paper_print_tip', 'drawing_type',
          'attachment_name', 'attachments', 'offices',
        ],
      },
      {
        title: '无合同号 · 投标/安装图',
        fieldIds: [
          'customer_name', 'matter',
          'dept_code', 'is_xiaomeng', 'design_card_no', 'drawing_issue_type', 'drawing_types',
          'pickup_purpose', 'apply_reason_star', 'biz_feedback',
          'lose_bid_reason', 'card_date', 'pre_designers', 'require_draw_date',
          'scheme_detail', 'install_env', 'install_position',
          'foundation_drawing', 'install_method', 'scheme_material',
          'attention', 'attachment_names', 'attachments_no_image',
          'offices_multi', 'transfer_sw_lwt',
        ],
      },
      {
        title: '备注',
        fieldIds: ['remark'],
      },
    ],
    spans: {
      scheme_type: 24,
      related_project: 24,
      related_customer: 24,
      serial_no: 12, apply_datetime: 12,
      apply_reason: 24, paper_print_tip: 24, attachments: 24, images: 24,
      scheme_detail: 24, install_env: 24, scheme_material: 24,
      apply_or_change: 24, apply_reason_star: 24, remark: 24, attention: 24,
      attachments_no_image: 24,
    },
  },
  // 生产卡/补充流程：分区对齐 JDY 分隔条；span = lineWidth×2
  prod_card_supplement: {
    contentMaxWidth: 1100,
    listColumns: [
      'card_date', 'department', 'submitter', 'product_type',
      'is_supplement', 'involve_outsource', 'is_shipped', 'contract_no_select',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'card_date', 'department', 'submitter', 'is_supplement',
          'involve_outsource', 'is_finance_only', 'is_shipped', 'involve_amount_change',
          'is_unit_change', 'is_robot', 'f_240503', 'increase_cost',
          'need_research_drawing', 'product_type', 'is_turnkey', 'responsible_party',
        ],
      },
      {
        title: '补充 / 合同信息',
        fieldIds: [
          'drawing_no_query', 'no_sales_person', 'no_drawing_no',
          'contract_no_select', 'paint_req_supplement',
          'yes_contract_no', 'yes_sales_person', 'yes_customer_name',
          'customer_sales_select', 'description', 'region_manager',
        ],
      },
      {
        title: '车间填写',
        fieldIds: ['std_room_fill', 'elec_workshop_fill'],
      },
      {
        title: '技术协议与附件',
        fieldIds: [
          'need_dispatch', 'need_elec_workshop', 'has_tech_agreement', 'tech_agreement_std',
          'attachments', 'images', 'confirm_agreement',
        ],
      },
      {
        title: '设计指派填写',
        fieldIds: [
          'design_dispatch', 'transfer_packaging_users', 'design_assignees', 'offices',
          'order_datetime', 'order_type', 'field',
          'has_install_project', 'f_251128', 'install_project_no', 'f_0414',
        ],
      },
      {
        title: '生产卡通知单上的内容',
        fieldIds: [
          'prod_card_line_items', 'packaging_req', 'project_name', 'paint_req',
          'tech_params', 'no_warranty_period', 'special_reminder',
          'remark_prod_card', 'special_reminder_multi',
        ],
      },
      {
        title: '合同技术协议评审',
        fieldIds: [
          'has_contract_tech_review', 'select_contract_tech_review', 'contract_tech_review_sn',
        ],
      },
    ],
    spans: {
      card_date: 6, department: 6, submitter: 6, is_supplement: 6,
      involve_outsource: 6, is_finance_only: 6, is_shipped: 6, involve_amount_change: 6,
      is_unit_change: 6, is_robot: 6, f_240503: 6, increase_cost: 6,
      need_research_drawing: 6, product_type: 6, is_turnkey: 6, responsible_party: 6,
      drawing_no_query: 24, no_sales_person: 6, no_drawing_no: 6,
      contract_no_select: 24, paint_req_supplement: 24,
      yes_contract_no: 6, yes_sales_person: 6, yes_customer_name: 6,
      customer_sales_select: 12, description: 24, region_manager: 12,
      std_room_fill: 24, elec_workshop_fill: 24,
      need_dispatch: 24, need_elec_workshop: 6, has_tech_agreement: 6, tech_agreement_std: 12,
      attachments: 12, images: 12, confirm_agreement: 24,
      design_dispatch: 12, transfer_packaging_users: 12, design_assignees: 12, offices: 12,
      order_datetime: 8, order_type: 8, field: 8,
      has_install_project: 6, f_251128: 24, install_project_no: 24, f_0414: 24,
      prod_card_line_items: 24,
      packaging_req: 8, project_name: 8, paint_req: 8,
      tech_params: 8, no_warranty_period: 6, special_reminder: 12,
      remark_prod_card: 8, special_reminder_multi: 8,
      has_contract_tech_review: 12, select_contract_tech_review: 12, contract_tech_review_sn: 12,
    },
  },
  // 开票申请（选合同号带出红框字段；已去掉合同明细变动）
  invoice_application: {
    contentMaxWidth: 1080,
    listColumns: [
      'serial_no', 'apply_date', 'customer_name', 'sales_person',
      'department', 'drawing_no', 'total_amount', 'invoice_no',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'apply_date', 'department', 'drawing_no_select',
          'drawing_no', 'customer_name', 'dept_contract_no', 'customer_no',
          'sales_person',
        ],
      },
      {
        title: '开票信息',
        fieldIds: [
          'taxpayer_id', 'invoice_address_phone', 'bank_account',
        ],
      },
      {
        title: '合同明细与合计',
        fieldIds: [
          'contract_data', 'contract_lines_new',
          'total_amount', 'total_amount_adjusted', 'customer_code',
        ],
      },
      {
        title: '开票与附件',
        fieldIds: [
          'invoice_datetime', 'invoice_special_req', 'invoice_no', 'remark',
          'invoice_email', 'attachments', 'images',
        ],
      },
    ],
    spans: {
      serial_no: 6, apply_date: 6, department: 6, drawing_no_select: 6,
      drawing_no: 6, customer_name: 12, dept_contract_no: 6, customer_no: 6,
      sales_person: 6,
      taxpayer_id: 8, invoice_address_phone: 8, bank_account: 8,
      contract_data: 24, contract_lines_new: 24,
      total_amount: 8, total_amount_adjusted: 8, customer_code: 8,
      invoice_datetime: 6, invoice_special_req: 18, invoice_no: 6, remark: 18,
      invoice_email: 8, attachments: 8, images: 8,
    },
  },
  // 收款登记（内勤填写对齐 JDY separator）
  payment_registration: {
    contentMaxWidth: 1080,
    listExpandDetail: 'payment_details',
    listColumns: [
      'payment_no', 'payment_date', 'customer_name', 'department',
      'payment_total', 'sales_person',
    ],
    sections: [
      {
        title: '来款信息',
        fieldIds: [
          'payment_no', 'payment_date', 'customer_name', 'department',
          'payment_details', 'payment_total',
        ],
      },
      {
        title: '内勤填写',
        fieldIds: [
          'sales_person', 'payment_allocation', 'alloc_total',
          'discount_docs', 'penalty_docs', 'images', 'remark_2',
        ],
      },
    ],
    spans: {
      payment_no: 6, payment_date: 6, customer_name: 6, department: 6,
      payment_details: 24, payment_total: 12,
      sales_person: 12, payment_allocation: 24, alloc_total: 6,
      discount_docs: 6, penalty_docs: 6, images: 6, remark_2: 24,
    },
  },
  // 报价管理（简道云核价管理流程）
  quote_management: {
    contentMaxWidth: 1080,
    listExpandDetail: 'price_lines',
    listColumns: [
      'customer_name', 'sales_person', 'department', 'price_type',
      'customer_category', 'ref_contract_no', 'need_purchase',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'department', 'sales_person', 'ref_contract_no',
          'customer_name', 'card_contract_no', 'customer_category', 'price_type',
        ],
      },
      {
        title: '价格明细',
        fieldIds: ['price_lines'],
      },
      {
        title: '采购与附件',
        fieldIds: [
          'need_purchase', 'purchaser',
          'inquiry_attachments', 'cost_attachments', 'inquiry_images',
          'special_reminder', 'cost_price',
        ],
      },
    ],
    spans: {
      serial_no: 6, department: 6, sales_person: 6, ref_contract_no: 6,
      customer_name: 12, card_contract_no: 6, customer_category: 6, price_type: 6,
      price_lines: 24,
      need_purchase: 6, purchaser: 6,
      inquiry_attachments: 8, cost_attachments: 8, inquiry_images: 8,
      special_reminder: 12, cost_price: 12,
    },
  },
  // 核价清单传递（中央研究院 HJQD）
  pricing_checklist_hjqd: {
    contentMaxWidth: 1080,
    listColumns: [
      'serial_no', 'process_name', 'contract_no', 'order_person',
      'applicant', 'business_dept', 'design_card_no', 'apply_datetime',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: ['serial_no', 'process_name'],
      },
      {
        title: '关联安装图设计通知',
        fieldIds: [
          'link_install', 'install_serial_no', 'install_design_card_no',
          'install_order_person', 'install_applicant', 'install_department',
        ],
      },
      {
        title: '关联合同图纸领用',
        fieldIds: [
          'link_requisition', 'req_serial_no', 'req_contract_no',
          'req_applicant', 'req_order_person', 'req_department',
        ],
      },
      {
        title: '关联客服领图',
        fieldIds: [
          'link_cs_drawing', 'cs_serial_no', 'cs_contract_no',
          'cs_order_person', 'cs_applicant', 'cs_department',
        ],
      },
      {
        title: '关联中央研究院协同卡',
        fieldIds: [
          'link_coop_card', 'coop_serial_no', 'coop_contract_no',
          'coop_order_person', 'coop_applicant', 'coop_order_dept',
        ],
      },
      {
        title: '核价清单',
        fieldIds: [
          'summary_serial_no', 'design_card_no', 'contract_no',
          'order_person', 'applicant', 'business_dept',
          'designer', 'office', 'apply_datetime', 'pricing_qty',
          'images', 'attachments', 'remark',
        ],
      },
      {
        title: '问题反馈（财务填写）',
        fieldIds: ['has_issue', 'issue_details'],
      },
    ],
    spans: {
      serial_no: 8, process_name: 16,
      link_install: 24, link_requisition: 24, link_cs_drawing: 24, link_coop_card: 24,
      install_serial_no: 8, install_design_card_no: 8, install_order_person: 8,
      install_applicant: 8, install_department: 8,
      req_serial_no: 8, req_contract_no: 8, req_applicant: 8,
      req_order_person: 8, req_department: 8,
      cs_serial_no: 8, cs_contract_no: 8, cs_order_person: 8,
      cs_applicant: 8, cs_department: 8,
      coop_serial_no: 8, coop_contract_no: 8, coop_order_person: 8,
      coop_applicant: 8, coop_order_dept: 8,
      summary_serial_no: 8, design_card_no: 8, contract_no: 8,
      order_person: 8, applicant: 8, business_dept: 8,
      designer: 8, office: 8, apply_datetime: 8, pricing_qty: 8,
      images: 12, attachments: 12, remark: 24,
      has_issue: 8, issue_details: 24,
    },
  },
  // —— 客户服务部（售后低代码，与原生售后工单并存）——
  // 列表列序对齐简道云「客户服务申请及反馈」数据管理横向滚动视图
  cs_service_request: {
    contentMaxWidth: 1100,
    listDetailMaxCols: 10,
    listExpandDetails: ['field_10', 'field_19'],
    listColumns: [
      'field', 'sales_person', 'field_2', 'customer_name',
      'field_3', 'field_4', 'field_5', 'field_6', 'field_7', 'remark',
      'field_8', 'field_9', 'field_18',
      'field_27', 'field_28',
      'field_29', 'field_30', 'field_31', 'field_32',
      'field_33', 'field_34', 'field_35', 'field_36',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'field', 'sales_person', 'field_2', 'customer_name',
          'field_3', 'field_4', 'field_5', 'field_6', 'field_7', 'remark',
          'field_8', 'field_9',
        ],
      },
      {
        title: '主要产品信息',
        fieldIds: ['field_10'],
      },
      {
        title: '其它待排查 / 排产产品',
        fieldIds: ['field_18', 'field_19'],
      },
      {
        title: '总工转交与附件',
        fieldIds: [
          'field_27', 'field_28',
          'field_29', 'field_30', 'field_31', 'field_32',
        ],
      },
      {
        title: '协作与转交（审批）',
        fieldIds: [
          'field_33', 'field_34', 'field_35', 'field_36',
          'field_37', 'field_38', 'field_39', 'field_40',
        ],
      },
      {
        title: '客服备注',
        fieldIds: ['field_41'],
      },
    ],
    spans: {
      // 基本信息：两列短字段 + 服务地点/要求/路线/性质整行（对齐简道云填报）
      serial_no: 12, field: 12, sales_person: 12, field_2: 12,
      customer_name: 12, field_3: 12,
      field_4: 24, field_5: 24, field_6: 24, field_7: 24, remark: 24,
      field_8: 12, field_9: 12,
      field_10: 24, field_18: 12, field_19: 24,
      field_29: 8, field_30: 8, field_31: 8, field_32: 24,
      field_41: 24,
    },
  },
  cs_product_replace: {
    contentMaxWidth: 1080,
    listColumns: [
      'customer_name', 'sales_person', 'field_2', 'field',
      'field_6', 'field_5', 'field_4', 'field_27',
    ],
    listExpandDetail: 'field_13',
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'field', 'field_2', 'sales_person', 'field_3',
          'customer_name', 'field_4', 'field_5', 'remark', 'field_6', 'field_7', 'field_27',
        ],
      },
      { title: '更换明细', fieldIds: ['field_13', 'field_22'] },
    ],
    spans: { remark: 24, field_13: 24, field_22: 24 },
  },
  cs_product_return: {
    contentMaxWidth: 1080,
    listColumns: [
      'customer_name', 'field_4', 'sales_person', 'field_5',
      'field', 'field_6', 'field_7', 'field_2',
    ],
    listExpandDetail: 'field_8',
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'field', 'field_2', 'field_3', 'field_4',
          'customer_name', 'field_5', 'sales_person', 'field_6', 'field_7', 'remark',
        ],
      },
      { title: '退回明细', fieldIds: ['field_8', 'field_16'] },
    ],
    spans: { remark: 24, field_8: 24, field_16: 24 },
  },
  cs_loan_slip: {
    contentMaxWidth: 960,
    listColumns: [
      'customer_name', 'contract_no', 'sales_person', 'field_2',
      'field', 'field_14', 'field_9', 'field_10',
    ],
    listExpandDetail: 'field_4',
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'field', 'customer_name', 'contract_no',
          'field_2', 'sales_person', 'field_3', 'field_14',
        ],
      },
      { title: '借据明细', fieldIds: ['field_4', 'field_11', 'field_12'] },
    ],
    spans: { field_4: 24 },
  },
  cs_service_delay: {
    contentMaxWidth: 960,
    listColumns: [
      'contract_no', 'sales_person', 'field', 'field_6',
      'field_7', 'field_8', 'field_9',
    ],
    listExpandDetail: 'field_2',
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'contract_no', 'sales_person', 'field',
          'field_6', 'field_7', 'field_8', 'field_9', 'remark',
        ],
      },
      { title: '设备信息', fieldIds: ['field_2'] },
    ],
    spans: { field_9: 24, remark: 24, field_2: 24 },
  },
  cs_correspondence: {
    contentMaxWidth: 960,
    listColumns: [
      'customer_name', 'contract_no', 'applicant', 'field',
      'sales_person', 'field_5', 'field_7',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'field', 'applicant', 'field_2', 'contract_no',
          'customer_name', 'field_5', 'sales_person', 'field_6', 'field_7',
        ],
      },
      { title: '函件附件', fieldIds: ['field_8'] },
    ],
    spans: { field_7: 24, field_8: 24 },
  },
}

/** 解析列表默认列字段 id（简道云式扫视列） */
export function resolveListColumnIds(templateCode?: string): string[] | undefined {
  if (!templateCode) return undefined
  const cols = DRAWING_FORM_LAYOUT[templateCode]?.listColumns
  return cols?.length ? cols : undefined
}

export function resolveListColumnWidths(templateCode?: string): Record<string, number> | undefined {
  if (!templateCode) return undefined
  return DRAWING_FORM_LAYOUT[templateCode]?.listColumnWidths
}

export function resolveListColumnLabels(templateCode?: string): Record<string, string> | undefined {
  if (!templateCode) return undefined
  return DRAWING_FORM_LAYOUT[templateCode]?.listColumnLabels
}

export function resolveListFullText(templateCode?: string): boolean {
  if (!templateCode) return false
  return !!DRAWING_FORM_LAYOUT[templateCode]?.listFullText
}

/** 解析列表应展开的明细表（可多个，对齐简道云多子表横向分组） */
export function resolveListExpandDetails(
  fields: FieldDefinition[],
  templateCode?: string,
): FieldDefinition[] {
  const byId = new Map(fields.map((f) => [f.id, f]))
  const out: FieldDefinition[] = []
  const seen = new Set<string>()
  const push = (f?: FieldDefinition) => {
    if (!f || f.type !== 'detail_table' || seen.has(f.id)) return
    seen.add(f.id)
    out.push(f)
  }
  for (const f of fields) {
    if (f.type === 'detail_table' && !!(f.props as { list_expand?: boolean } | undefined)?.list_expand) {
      push(f)
    }
  }
  const layout = templateCode ? DRAWING_FORM_LAYOUT[templateCode] : undefined
  const ids = layout?.listExpandDetails?.length
    ? layout.listExpandDetails
    : (layout?.listExpandDetail ? [layout.listExpandDetail] : [])
  for (const id of ids) push(byId.get(id))
  return out
}

/** 兼容旧调用：取第一个展开明细 */
export function resolveListExpandDetail(
  fields: FieldDefinition[],
  templateCode?: string,
): FieldDefinition | undefined {
  return resolveListExpandDetails(fields, templateCode)[0]
}

const SHORT_TYPES = new Set([
  'text', 'select', 'radio', 'person', 'person_multi',
  'department', 'department_multi', 'date', 'datetime', 'number',
  'amount', 'multi_select', 'switch', 'formula', 'auto_number', 'project', 'contract', 'customer',
  'tech_agreement_review',
])

function defaultSpan(field: FieldDefinition): number {
  if (field.type === 'detail_table' || field.type === 'textarea' || field.type === 'file'
    || field.type === 'image' || field.type === 'checkbox' || field.type === 'rich_text'
    || field.type === 'address' || field.type === 'cascade' || field.type === 'signature') {
    return 24
  }
  if (SHORT_TYPES.has(field.type)) return 12
  return 24
}

/** Inject section markers + apply spans; keep unknown fields at end under 「其它」 */
export function applyDrawingFormLayout(
  templateCode: string | undefined,
  fields: FieldDefinition[],
): FieldDefinition[] {
  if (!templateCode) return fields
  const layout = DRAWING_FORM_LAYOUT[templateCode]
  if (!layout) return fields

  const byId = new Map(fields.map((f) => [f.id, f]))
  const used = new Set<string>()
  const out: FieldDefinition[] = []
  const spans = layout.spans || {}

  const withSpan = (f: FieldDefinition): FieldDefinition => ({
    ...f,
    span: spans[f.id] ?? f.span ?? defaultSpan(f),
  })

  for (const sec of layout.sections) {
    const matched = sec.fieldIds
      .map((id) => byId.get(id))
      .filter((f): f is FieldDefinition => !!f && !used.has(f.id))
    if (!matched.length) continue
    out.push({
      id: `__section_${sec.title}`,
      type: 'section',
      label: sec.title,
      span: 24,
    })
    for (const f of matched) {
      used.add(f.id)
      let next = withSpan(f)
      // 分区标题与唯一明细表同名时去掉字段标签，避免「主要产品信息」重复两行
      if (
        matched.length === 1
        && f.type === 'detail_table'
        && (f.label || '') === sec.title
      ) {
        next = { ...next, label: '' }
      }
      out.push(next)
    }
  }

  const rest = fields.filter((f) => !used.has(f.id))
  if (rest.length) {
    out.push({
      id: '__section_其它',
      type: 'section',
      label: '其它',
      span: 24,
    })
    for (const f of rest) out.push(withSpan(f))
  }
  return out
}
