// 图纸 / 方案 / 生产卡 / 开票 / 收款：分区布局 + 栅格 span（对齐简道云 lineWidth，×2 为 antd Col span）
import type { FieldDefinition } from '@/types/lowcode'

/** title 为空时不插入分区标题，字段续接上一段栅格 */
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
  /** 填报页字段标签覆盖（修正租户旧版误标，如业务部门标成日期时间） */
  fieldLabels?: Record<string, string>
  /**
   * 列表单元格不截断省略号，横向滚动看全（对齐简道云数据管理）。
   */
  listFullText?: boolean
  /** 明细子列展示上限（默认 8；产品明细可调高） */
  listDetailMaxCols?: number
}

export const DRAWING_FORM_LAYOUT: Record<string, DrawingFormLayoutSpec> = {
  /** 合同图纸对应表：对齐简道云一行四列 + 无分区标题 */
  contract_drawing_map: {
    contentMaxWidth: 1100,
    listColumns: [
      'pre_issue', 'apply_date', 'number_attr', 'contract_no',
      'department', 'drawing_no', 'remark',
    ],
    listFullText: true,
    listColumnWidths: {
      pre_issue: 72,
      apply_date: 118,
      number_attr: 88,
      contract_no: 140,
      department: 200,
      drawing_no: 150,
      remark: 220,
    },
    sections: [
      {
        title: '',
        fieldIds: [
          'pre_issue', 'apply_date', 'number_attr', 'contract_no',
          'department', 'drawing_no', 'remark',
        ],
      },
    ],
    // 简道云 lineWidth≈6 → span 6（一行四列）；备注通栏
    spans: {
      pre_issue: 6,
      apply_date: 6,
      number_attr: 6,
      contract_no: 6,
      department: 6,
      drawing_no: 6,
      remark: 24,
    },
  },
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
      'serial_no', 'card_date', 'department', 'submitter', 'product_type',
      'is_supplement', 'involve_outsource', 'is_shipped', 'contract_no_select',
    ],
    listColumnLabels: {
      contract_no_select: '选择合同',
    },
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'card_date', 'department', 'submitter', 'is_supplement',
          'involve_outsource', 'is_finance_only', 'is_shipped', 'involve_amount_change',
          'is_unit_change', 'is_robot', 'f_240503', 'increase_cost',
          'need_research_drawing', 'product_type', 'is_turnkey', 'responsible_party',
        ],
      },
      {
        title: '补充 / 合同信息',
        fieldIds: [
          'drawing_no_query',
          'no_drawing_no',
          'no_sales_person',
          'yes_customer_name',
          'contract_delivery_date',
          'project_name',
          'packaging_req',
          'special_reminder',
          'prod_card_line_items',
          'remark_prod_card',
          'paint_req',
          'has_intelligence',
          'is_export_equipment',
          'tech_params',
          'no_warranty_period',
          'region_manager',
          'contract_no_select',
          'paint_req_supplement',
          'yes_contract_no',
          'yes_sales_person',
          'customer_sales_select',
          'description',
          'has_install_project', 'f_251128', 'install_project_no',
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
        ],
      },
      {
        title: '生产卡通知单上的内容',
        fieldIds: [
          'special_reminder_multi',
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
      serial_no: 6, card_date: 6, department: 6, submitter: 6, is_supplement: 6,
      involve_outsource: 6, is_finance_only: 6, is_shipped: 6, involve_amount_change: 6,
      is_unit_change: 6, is_robot: 6, f_240503: 6, increase_cost: 6,
      need_research_drawing: 6, product_type: 6, is_turnkey: 6, responsible_party: 6,
      drawing_no_query: 24,
      yes_customer_name: 12,
      no_drawing_no: 6,
      contract_delivery_date: 6,
      project_name: 12,
      packaging_req: 12,
      prod_card_line_items: 24,
      paint_req: 6,
      has_intelligence: 6,
      is_export_equipment: 6,
      no_warranty_period: 6,
      special_reminder: 12,
      tech_params: 12,
      remark_prod_card: 12,
      no_sales_person: 6,
      region_manager: 6,
      contract_no_select: 24,
      paint_req_supplement: 24,
      yes_contract_no: 6,
      yes_sales_person: 6,
      customer_sales_select: 12, description: 24,
      std_room_fill: 24, elec_workshop_fill: 24,
      need_dispatch: 24, need_elec_workshop: 6, has_tech_agreement: 6, tech_agreement_std: 12,
      attachments: 12, images: 12, confirm_agreement: 24,
      design_dispatch: 12, transfer_packaging_users: 12, design_assignees: 12, offices: 12,
      order_datetime: 8, order_type: 8, field: 8,
      has_install_project: 6, f_251128: 24, install_project_no: 24,
      special_reminder_multi: 8,
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
    // 不在列表展开来款明细：展开后 flat 行数与分页 total（主单数）不一致，
    // 用户会感觉「少了很多单」；来款/分款明细在详情页查看。
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
    // 不在列表展开价格明细：rowSpan 合并 + 右侧固定列会导致行高错位、状态列叠字，
    // 用户滚动时像「少了很多单」（尤其 8/15 等靠后记录）。明细仍在详情页查看。
    listColumns: [
      'related_project', 'customer_name', 'sales_person', 'department', 'price_type',
      'customer_category', 'ref_contract_no', 'need_purchase',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'department', 'sales_person', 'ref_contract_no',
          'related_project', 'customer_name', 'card_contract_no',
          'customer_category', 'price_type',
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
      related_project: 12, customer_name: 12, card_contract_no: 6,
      customer_category: 6, price_type: 6,
      price_lines: 24,
      need_purchase: 6, purchaser: 6,
      inquiry_attachments: 24, cost_attachments: 24, inquiry_images: 24,
      special_reminder: 12, cost_price: 12,
    },
  },
  // 售前服务通知（销售中心；grid-4，span = 简道云 lineWidth×2）
  presale_service_notice: {
    contentMaxWidth: 1100,
    listColumns: [
      'serial_no', 'applicant', 'department', 'is_smart',
      'need_jwx_onsite', 'service_location', 'service_time',
      'contract_no', 'project_status', 'smart_project_status',
    ],
    listFullText: true,
    listColumnWidths: {
      serial_no: 160,
      applicant: 88,
      department: 200,
      is_smart: 96,
      need_jwx_onsite: 150,
      service_location: 200,
      service_time: 118,
      contract_no: 220,
      project_status: 110,
      smart_project_status: 130,
    },
    sections: [
      {
        title: '基本信息（创建时填写）',
        fieldIds: [
          'serial_no', 'applicant', 'department', 'is_smart',
          'need_jwx_onsite', 'project_status', 'smart_project_status',
          'attachments', 'desired_staff', 'contract_no',
        ],
      },
      {
        title: '服务信息',
        fieldIds: [
          'service_location', 'service_time', 'estimated_days', 'contact_phone',
          'drawing_tech_status', 'service_content',
          'work_schedule', 'remark',
        ],
      },
      {
        title: '测绘（审批时填写）',
        fieldIds: [
          'staff_coordination', 'product_name', 'spec_model', 'surveyor',
          'survey_data', 'need_xjwm_staff', 'xjwm_staff', 'other_notes',
        ],
      },
    ],
    spans: {
      serial_no: 6, applicant: 6, department: 6, is_smart: 6,
      need_jwx_onsite: 6, project_status: 6, smart_project_status: 6,
      attachments: 6, desired_staff: 6, contract_no: 6,
      service_location: 6, service_time: 6, estimated_days: 6, contact_phone: 6,
      drawing_tech_status: 6, service_content: 18,
      work_schedule: 24, remark: 24,
      staff_coordination: 6, product_name: 6, spec_model: 6, surveyor: 6,
      survey_data: 24,
      need_xjwm_staff: 6, xjwm_staff: 6, other_notes: 24,
    },
  },
  // 发货通知（销售中心「CRM-发货通知流程」）
  shipment_notice: {
    contentMaxWidth: 1100,
    listColumns: [
      'serial_no', 'ship_type', 'ship_status', 'contract_no',
      'department', 'sales_person', 'consignee_unit', 'require_arrive_time',
    ],
    listFullText: true,
    listColumnWidths: {
      serial_no: 160,
      ship_type: 96,
      ship_status: 88,
      contract_no: 200,
      department: 160,
      sales_person: 88,
      consignee_unit: 180,
      require_arrive_time: 118,
    },
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'biz_datetime', 'ship_type', 'purchasers',
          'ship_status', 'is_after_sales', 'purchaser', 'contract_no',
          'need_install', 'counterparty_contract_no', 'contract_amount',
          'shipped_amount_incl', 'unshipped_amount', 'contract_no_text',
          'dept_contract_no', 'exit_pass_no', 'department', 'sales_person',
          'sales_phone',
        ],
      },
      {
        title: '收货与运输',
        fieldIds: [
          'consignee_unit', 'consignee_contact', 'require_arrive_time',
          'multi_unload', 'address', 'address_2', 'freight_payer',
          'holiday_receive', 'need_weigh', 'is_reship', 'need_return_goods',
          'return_goods_content', 'truck_limit', 'allow_other_goods',
          'payment_method',
        ],
      },
      {
        title: '发货明细',
        fieldIds: ['ship_lines', 'ship_amount', 'notes'],
      },
      {
        title: '仓库 / 出库（审批填写）',
        fieldIds: [
          'is_sales_outbound', 'warehouse_handler', 'warehouse_transfer',
          'pack_first', 'finance_check_note',
        ],
      },
      {
        title: '验收与回执',
        fieldIds: [
          'accept_method', 'accept_docs', 'accept_attachments',
          'attachments', 'images', 'receipt_images', 'receipt_files',
        ],
      },
    ],
    spans: {
      serial_no: 6, biz_datetime: 6, ship_type: 6, purchasers: 6,
      ship_status: 6, is_after_sales: 6, purchaser: 6, contract_no: 6,
      need_install: 6, counterparty_contract_no: 6, contract_amount: 6,
      shipped_amount_incl: 6, unshipped_amount: 6, contract_no_text: 6,
      dept_contract_no: 6, exit_pass_no: 6, department: 6, sales_person: 6,
      sales_phone: 6,
      consignee_unit: 12, consignee_contact: 12, require_arrive_time: 6,
      multi_unload: 6, address: 12, address_2: 12, freight_payer: 6,
      holiday_receive: 6, need_weigh: 6, is_reship: 6, need_return_goods: 6,
      return_goods_content: 24, truck_limit: 6, allow_other_goods: 6,
      payment_method: 6,
      ship_lines: 24, ship_amount: 6, notes: 18,
      is_sales_outbound: 6, warehouse_handler: 6, warehouse_transfer: 6,
      pack_first: 6, finance_check_note: 12,
      accept_method: 6, accept_docs: 6, accept_attachments: 12,
      attachments: 12, images: 12, receipt_images: 12, receipt_files: 12,
    },
  },
  // 业务奖金流转单（简道云 lineWidth=12 通栏）
  biz_bonus_transfer: {
    contentMaxWidth: 960,
    listColumns: [
      'bonus_no', 'bonus_date', 'drawing_no', 'salesperson', 'department',
      'company_name', 'current_bonus', 'payment_total',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'bonus_no', 'bonus_date', 'drawing_no', 'salesperson', 'department',
          'sign_date', 'company_name',
        ],
      },
      {
        title: '合同信息',
        fieldIds: [
          'contract_lines', 'contract_amount', 'payment_method',
          'attachments', 'images',
        ],
      },
      {
        title: '来款情况',
        fieldIds: [
          'payment_lines', 'payment_total', 'settle_pct', 'settle_status',
        ],
      },
      {
        title: '费用与奖金',
        fieldIds: [
          'freight', 'service_fee', 'entertainment_fee', 'rebate',
          'drawn_ratio', 'field_11', 'drawn_bonus', 'field_12',
          'current_bonus', 'amount_cn', 'remark',
        ],
      },
      {
        title: '审批与支付',
        fieldIds: ['field_13', 'payment_status', 'submitter_aux'],
      },
    ],
    spans: {
      bonus_no: 24, bonus_date: 24, drawing_no: 24, salesperson: 24, department: 24,
      sign_date: 24, company_name: 24,
      contract_lines: 24, contract_amount: 24, payment_method: 24,
      attachments: 24, images: 24,
      payment_lines: 24, payment_total: 24, settle_pct: 24, settle_status: 24,
      freight: 24, service_fee: 24, entertainment_fee: 24, rebate: 24,
      drawn_ratio: 24, field_11: 24, drawn_bonus: 24, field_12: 24,
      current_bonus: 24, amount_cn: 24, remark: 24,
      field_13: 24, payment_status: 24, submitter_aux: 24,
    },
  },
  // 业务奖金流转—业务发起（部门在业务员前；简道云通栏）
  biz_bonus_biz_initiate: {
    contentMaxWidth: 960,
    listColumns: [
      'bonus_no', 'bonus_date', 'drawing_no', 'department', 'salesperson',
      'company_name', 'current_bonus', 'field_19',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'bonus_no', 'bonus_date', 'drawing_no', 'department', 'salesperson',
          'field', 'sign_date', 'company_name',
        ],
      },
      {
        title: '合同信息',
        fieldIds: [
          'contract_lines', 'contract_amount', 'payment_method',
          'attachments', 'images',
        ],
      },
      {
        title: '来款情况',
        fieldIds: [
          'payment_lines', 'payment_total', 'settle_pct', 'settle_status',
        ],
      },
      {
        title: '费用与奖金',
        fieldIds: [
          'freight', 'service_fee', 'entertainment_fee', 'rebate',
          'drawn_ratio', 'field_12', 'drawn_bonus', 'field_13',
          'current_bonus', 'amount_cn', 'remark',
        ],
      },
      {
        title: '审批与支付',
        fieldIds: ['field_14', 'payment_status', 'submitter_aux', 'field_19'],
      },
    ],
    spans: {
      bonus_no: 24, bonus_date: 24, drawing_no: 24, department: 24, salesperson: 24,
      field: 24, sign_date: 24, company_name: 24,
      contract_lines: 24, contract_amount: 24, payment_method: 24,
      attachments: 24, images: 24,
      payment_lines: 24, payment_total: 24, settle_pct: 24, settle_status: 24,
      freight: 24, service_fee: 24, entertainment_fee: 24, rebate: 24,
      drawn_ratio: 24, field_12: 24, drawn_bonus: 24, field_13: 24,
      current_bonus: 24, amount_cn: 24, remark: 24,
      field_14: 24, payment_status: 24, submitter_aux: 24, field_19: 24,
    },
  },
  // 提成数据库（简道云 grid-2，lineWidth 6 → span 12）
  commission_database: {
    contentMaxWidth: 1080,
    listColumns: [
      'commission_date', 'bonus_no', 'company_name', 'salesperson',
      'department', 'contract_no', 'contract_amount', 'current_bonus',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'commission_date', 'bonus_no', 'company_name', 'salesperson',
          'department', 'contract_no', 'contract_amount',
        ],
      },
      {
        title: '来款与费用',
        fieldIds: [
          'payment_lines', 'payment_total', 'field_4',
          'service_fee', 'entertainment_fee', 'freight',
        ],
      },
      {
        title: '结算与奖金',
        fieldIds: [
          'settle_status', 'drawn_ratio', 'drawn_bonus', 'current_bonus',
        ],
      },
      {
        title: '支付状态',
        fieldIds: ['payment_status', 'field_9'],
      },
    ],
    spans: {
      commission_date: 12, bonus_no: 12, company_name: 12, salesperson: 12,
      department: 12, contract_no: 12, contract_amount: 12,
      payment_lines: 24, payment_total: 12, field_4: 12,
      service_fee: 12, entertainment_fee: 12, freight: 12,
      settle_status: 12, drawn_ratio: 12, drawn_bonus: 12, current_bonus: 12,
      payment_status: 24, field_9: 12,
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
  // 技术协议反馈单（中央研究院）
  tech_agreement_feedback: {
    contentMaxWidth: 1080,
    listColumns: [
      'serial_no', 'applicant', 'office', 'contract_no', 'order_person',
      'department', 'design_reviewer', 'design_dispatch', 'notify_purchase',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'apply_datetime', 'applicant', 'office',
          'contract_no', 'order_person', 'department',
        ],
      },
      {
        title: '审核与分派',
        fieldIds: [
          'design_reviewer', 'notify_purchase', 'design_dispatch',
          'transfer_rd_centers', 'dept_clerk', 'salesperson',
        ],
      },
      {
        title: '协议与反馈',
        fieldIds: [
          'agreement_content', 'business_feedback', 'feedback_suggestion',
          'attachments', 'images',
        ],
      },
    ],
    spans: {
      serial_no: 6, apply_datetime: 6, applicant: 6, office: 6,
      contract_no: 6, order_person: 6, department: 6,
      design_reviewer: 6, notify_purchase: 6, design_dispatch: 6,
      transfer_rd_centers: 6, dept_clerk: 6, salesperson: 6,
      agreement_content: 12, business_feedback: 12, feedback_suggestion: 12,
      attachments: 12, images: 12,
    },
  },
  // 合同外购件提前安排流程（数据中心）
  contract_outsource_early: {
    contentMaxWidth: 1080,
    listExpandDetail: 'equipment_details',
    listColumns: [
      'serial_no', 'link_prod_card', 'prod_card_serial', 'contract_no',
      'salesperson', 'department', 'business_desc',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'apply_datetime', 'link_prod_card', 'prod_card_serial',
          'salesperson', 'department', 'contract_no',
        ],
      },
      {
        title: '设计分派',
        fieldIds: [
          'design_assign', 'office', 'transfer_dept_heads', 'transfer_dept_head',
          'designer_single', 'designer_multi', 'purchaser_multi',
        ],
      },
      {
        title: '业务说明',
        fieldIds: ['business_desc', 'remark', 'attachments'],
      },
      {
        title: '设备明细',
        fieldIds: ['equipment_details'],
      },
    ],
    spans: {
      serial_no: 6, apply_datetime: 6, link_prod_card: 6, prod_card_serial: 6,
      salesperson: 6, department: 6, contract_no: 6,
      design_assign: 6, office: 6, transfer_dept_heads: 6, transfer_dept_head: 6,
      designer_single: 6, designer_multi: 6, purchaser_multi: 6,
      business_desc: 12, remark: 12, attachments: 12,
      equipment_details: 24,
    },
  },
  // 中央研究院协同卡
  research_coop_card: {
    contentMaxWidth: 1080,
    listColumns: [
      'serial_no', 'coop_card_type', 'process_name', 'drawing_no',
      'order_person', 'applicant', 'office', 'design_dispatch',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: ['serial_no', 'coop_card_type'],
      },
      {
        title: '原始流程名称',
        fieldIds: ['process_name'],
      },
      {
        title: '关联安装图设计通知',
        fieldIds: [
          'link_install', 'install_serial_no', 'install_order_person',
          'install_applicant', 'install_design_card_no', 'install_project_no',
          'install_department',
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
          'link_cs_drawing', 'cs_serial_no', 'cs_department',
          'cs_applicant', 'cs_contract_no', 'cs_order_person',
        ],
      },
      {
        title: '关联生产卡/补充流程',
        fieldIds: [
          'link_prod_card', 'prod_card_no', 'prod_drawing_no',
          'prod_applicant', 'prod_department',
        ],
      },
      {
        title: '合并信息',
        fieldIds: [
          'merged_serial_no', 'project_no', 'design_card_no', 'contract_no',
          'order_person_merged', 'applicant_merged', 'business_dept_merged',
        ],
      },
      {
        title: '合同信息',
        fieldIds: [
          'link_contract', 'order_dept', 'order_person', 'drawing_no',
        ],
      },
      {
        title: '协同内容',
        fieldIds: [
          'card_date', 'drawing_no_generic', 'order_dept_generic',
          'order_person_generic', 'applicant', 'office',
          'equipment_name', 'spec_model', 'equipment_qty',
          'need_tech_agreement', 'coop_draw_due', 'full_draw_date',
        ],
      },
      {
        title: '电气',
        fieldIds: [
          'elec_motors', 'elec_motors_2', 'process_req', 'external_meters',
        ],
      },
      {
        title: '激振器',
        fieldIds: [
          'vibrator_params', 'vibrator_params_2', 'vibrator_params_3',
        ],
      },
      {
        title: '筛板',
        fieldIds: ['screen_deck', 'screen_type'],
      },
      {
        title: '标准化',
        fieldIds: ['std_due_date', 'std_summary', 'std_detail', 'chief_design_note'],
      },
      {
        title: '通用与包装',
        fieldIds: [
          'coop_project_name', 'delivery_draw_date', 'has_tech_agreement',
          'coop_content', 'attachment_names', 'attachments', 'images',
        ],
      },
      {
        title: '设计安排（审批填写）',
        fieldIds: [
          'design_dispatch', 'transfer_packaging_users', 'design_assignees',
          'offices', 'order_datetime',
        ],
      },
    ],
    spans: {
      serial_no: 8, coop_card_type: 16, process_name: 24,
      link_install: 24, link_requisition: 24, link_cs_drawing: 24, link_prod_card: 24,
      link_contract: 24,
      install_serial_no: 8, install_order_person: 8, install_applicant: 8,
      install_design_card_no: 8, install_project_no: 8, install_department: 8,
      req_serial_no: 8, req_contract_no: 8, req_applicant: 8,
      req_order_person: 8, req_department: 8,
      cs_serial_no: 8, cs_department: 8, cs_applicant: 8,
      cs_contract_no: 8, cs_order_person: 8,
      prod_card_no: 8, prod_drawing_no: 8, prod_applicant: 8, prod_department: 8,
      merged_serial_no: 8, project_no: 8, design_card_no: 8, contract_no: 8,
      order_person_merged: 8, applicant_merged: 8, business_dept_merged: 8,
      order_dept: 8, order_person: 8, drawing_no: 8,
      card_date: 8, drawing_no_generic: 8, order_dept_generic: 8,
      order_person_generic: 8, applicant: 8, office: 8,
      equipment_name: 8, spec_model: 8, equipment_qty: 8,
      need_tech_agreement: 8, coop_draw_due: 8, full_draw_date: 8,
      elec_motors: 24, elec_motors_2: 24, process_req: 12, external_meters: 12,
      vibrator_params: 24, vibrator_params_2: 24, vibrator_params_3: 24,
      screen_deck: 24, screen_type: 24,
      std_due_date: 8, std_summary: 16, std_detail: 24, chief_design_note: 24,
      coop_project_name: 12, delivery_draw_date: 6, has_tech_agreement: 6,
      coop_content: 24, attachment_names: 24, attachments: 12, images: 12,
      design_dispatch: 8, transfer_packaging_users: 8, design_assignees: 8,
      offices: 8, order_datetime: 8,
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
    contentMaxWidth: 1200,
    fieldLabels: {
      field: '业务部门',
      serial_no: '流水号',
      f_0418: '附件',
    },
    listColumns: [
      'serial_no', 'apply_datetime', 'field', 'sales_person', 'field_2',
      'customer_name', 'customer_category', 'field_3', 'field_4', 'field_5', 'field_6', 'field_24', 'remark',
    ],
    listExpandDetail: 'field_12',
    listDetailMaxCols: 8,
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          // 简道云 4 列栅格（lineWidth=3 → antd span 6）
          'serial_no', 'apply_datetime', 'field', 'sales_person',
          'field_2', 'customer_name', 'customer_category', 'field_3',
          'field_4', 'remark',
          'field_5', 'field_6',
        ],
      },
      {
        title: '换货（含补发）',
        fieldIds: ['field_12'],
      },
      {
        title: '图片',
        fieldIds: ['images'],
      },
      {
        // 简道云：附件 + 是否小萌 + 图片0418（lineWidth 3+3+6）
        title: '',
        fieldIds: ['f_0418', 'field_24', 'f_0418_5'],
      },
      {
        title: '审批填写',
        fieldIds: [
          'field_7', 'field_8', 'field_9', 'field_10', 'field_11', 'field_20',
          'f_0418_2', 'f_0418_3', 'f_0418_4',
          'field_22', 'field_23', 'field_25', 'field_26', 'field_27', 'field_28', 'field_29',
        ],
      },
      {
        title: '客服备注',
        fieldIds: ['field_30'],
      },
    ],
    spans: {
      serial_no: 6, apply_datetime: 6, field: 6, sales_person: 6,
      field_2: 6, customer_name: 6, customer_category: 6, field_3: 6,
      // lineWidth×2：3→6，4→8，6→12，12→24
      field_4: 6, remark: 12,
      field_5: 8, field_6: 8,
      field_12: 24,
      images: 24,
      f_0418: 6, field_24: 6, f_0418_5: 12,
      field_7: 8, field_8: 8, field_9: 8, field_10: 8, field_11: 8, field_20: 12,
      f_0418_2: 6, f_0418_3: 6, f_0418_4: 6, field_22: 6,
      field_23: 6, field_25: 6, field_26: 12,
      field_27: 6, field_28: 6, field_29: 6,
      field_30: 24,
    },
  },
  cs_product_return: {
    contentMaxWidth: 1200,
    fieldLabels: {
      field: '提交人',
      field_2: '发起部门',
      field_3: '类型',
      field_4: '业务部门',
      field_5: '现场联系人及电话',
      field_6: '货物地址',
      images_4: '图片',
      attachments: '附件',
      images_5: '图片',
      f_1: '仓库判定1',
    },
    // 简道云 grid-4 + showFields 列序
    listColumns: [
      'serial_no', 'apply_datetime', 'field_3', 'customer_name', 'field_4',
      'sales_person', 'field_5', 'field_6', 'remark',
    ],
    listExpandDetail: 'field_7',
    listDetailMaxCols: 8,
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'apply_datetime', 'field', 'field_2',
          'field_3', 'customer_name',
          'field_4', 'sales_person',
          'field_5', 'field_6', 'remark',
        ],
      },
      {
        title: '售出产品退回',
        fieldIds: ['field_7'],
      },
      {
        title: '图片',
        fieldIds: ['images'],
      },
      {
        title: '发起节点上传退回图片',
        fieldIds: ['field_16'],
      },
      {
        title: '',
        fieldIds: ['images_4', 'attachments', 'images_5'],
      },
      {
        title: '审批填写',
        fieldIds: [
          'field_18', 'field_19', 'field_20', 'field_21', 'field_22',
          'field_23', 'f_1', 'field_24', 'field_25',
        ],
      },
      {
        title: '转交相关人员',
        fieldIds: ['field_26', 'field_27'],
      },
    ],
    spans: {
      // 简道云 grid-4：lineWidth×2 → antd span
      serial_no: 6, apply_datetime: 6, field: 6, field_2: 6,
      field_3: 12, customer_name: 12,
      field_4: 6, sales_person: 6,
      field_5: 12, field_6: 12, remark: 12,
      field_7: 24, images: 24, field_16: 24,
      images_4: 12, attachments: 12, images_5: 12,
      field_18: 12,
      field_19: 8, field_20: 6, field_21: 6, field_22: 6,
      field_23: 6, f_1: 6,
      field_24: 12, field_25: 12,
      field_26: 6, field_27: 6,
    },
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
  cs_drawing_request: {
    contentMaxWidth: 960,
    listColumns: [
      'contract_no', 'applicant', 'department', 'order_person',
      'apply_reason_2', 'designer', 'product_model', 'transfer_channel',
    ],
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'apply_datetime', 'department', 'applicant',
          'contract_no', 'drawing_no_note', 'order_person',
          'apply_reason', 'apply_reason_2', 'designer', 'product_model',
        ],
      },
      {
        title: '图纸传递',
        fieldIds: [
          'transfer_channel', 'attachment_name', 'attachments', 'images',
          'dept_dispatch', 'design_dispatch', 'design_assignees', 'transfer_packaging_users',
          'offices', 'order_date',
        ],
      },
    ],
    spans: {
      apply_reason: 24, apply_reason_2: 24, attachments: 24, images: 24,
      design_assignees: 24, transfer_packaging_users: 24,
    },
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
  const fieldLabels = layout.fieldLabels || {}

  const withSpan = (f: FieldDefinition): FieldDefinition => ({
    ...f,
    label: fieldLabels[f.id] ?? f.label,
    span: spans[f.id] ?? f.span ?? defaultSpan(f),
  })

  for (const sec of layout.sections) {
    const matched = sec.fieldIds
      .map((id) => byId.get(id))
      .filter((f): f is FieldDefinition => !!f && !used.has(f.id))
    if (!matched.length) continue
    if (sec.title) {
      out.push({
        id: `__section_${sec.title}`,
        type: 'section',
        label: sec.title,
        span: 24,
      })
    }
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
