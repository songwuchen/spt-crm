"""合同登记「单表全览」导出 — 对齐 scripts/_export_contracts_*_205.py 列结构。"""
from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contract.models import Contract, ContractVersion
from app.domains.lowcode.native_field_catalog import (
    _CONTRACT_LINE_COLUMNS,
    _CONTRACT_PAY_COLUMNS,
)

ExportCellFn = Callable[[str, Any], Any]

LINE_COLS: list[tuple[str, str]] = [
    (c["id"], c.get("label") or c["id"]) for c in _CONTRACT_LINE_COLUMNS if c.get("id")
]
PAY_COLS: list[tuple[str, str]] = [
    (c["id"], c.get("label") or c["id"]) for c in _CONTRACT_PAY_COLUMNS if c.get("id")
]

ATT_SLOTS = {
    "contract_agreement": "合同/协议",
    "contract_image": "合同图片",
    "contract_acceptance": "验收单",
    "contract_accept_docs": "验收资料",
    "contract_other": "其他附件",
}
ATT_BIZ_CN = {
    "contract": "合同附件",
    **ATT_SLOTS,
    "contract_review": "合同评审附件",
}

STATUS_CN = {
    "draft": "草稿",
    "submitted": "已提交",
    "signed": "已签订",
    "terminated": "已终止",
    "approved": "已通过",
    "rejected": "已驳回",
    "withdrawn": "已撤回",
    "running": "审批中",
    "completed": "已完成",
    "pending": "待办",
    "waiting": "等待中",
    "cancelled": "已取消",
}
CHANGE_TYPE_CN = {"new": "新增", "change": "变动"}
ACTION_CN = {
    "submit": "提交",
    "approve": "通过",
    "reject": "驳回",
    "transfer": "转办",
    "withdraw": "撤回",
    "return": "退回",
    "comment": "评论",
}

REG_FIELDS: list[tuple[str, str]] = [
    ("change_reason", "变动原因"),
    ("review_sn", "合同/项目评审流水号"),
    ("review_sn_xm", "小萌合同评审流水号"),
    ("factory_no", "出厂编号"),
    ("contract_type", "合同类型"),
    ("project_name", "项目名称"),
    ("tax_included", "是否含税"),
    ("is_export", "设备是否出口"),
    ("need_install", "是否需要安装"),
    ("info_complete", "信息是否齐全"),
    ("missing_items", "缺少项"),
    ("info_incomplete_note", "信息不齐全备注"),
    ("export_type", "出口类型"),
    ("contract_form", "合同形式"),
    ("standard_delivery", "是否标准交付"),
    ("delivery_mode", "方式"),
    ("is_rotary_sieve", "是否为旋振筛"),
    ("industry", "行业分类"),
    ("region", "地区"),
    ("application_field", "应用领域"),
    ("application_material", "应用物料"),
    ("payment_forms", "付款形式"),
    ("payment_desc", "付款方式文字描述"),
    ("delivery_clause", "交货期条款"),
    ("warranty_period", "质保期限"),
    ("warranty_amount", "质保金额"),
    ("paint_req", "油漆要求"),
    ("workload", "工作量"),
    ("freight_payer", "运费承担方"),
    ("contract_address", "合同约定地址"),
    ("accept_method", "验收方式"),
    ("accept_materials", "验收所需资料"),
    ("accept_date", "验收日期"),
    ("has_intelligence", "是否含智能化"),
    ("smart_points", "智能点"),
    ("remark", "备注"),
    ("special_note", "特别提醒"),
    ("packaging", "包装情况"),
    ("tech_requirements", "技术参数及要求(登记)"),
    ("submitter", "登记提交人"),
]


def flat_export_headers() -> list[str]:
    head = [
        "数据来源", "流水号", "提交人", "下卡日期", "客户编号", "单位名称", "部门", "业务人员",
        "单据状态", "新增/变动", "合同获取信息方式", "合同号", "图纸编号", "对方合同号",
        "合同总金额", "订货日期", "签订日期", "合同交货期", "到期日期",
    ]
    head += [label for _, label in REG_FIELDS]
    head += [
        "版本状态", "流程状态", "当前待办节点", "当前处理人",
        "收款计划汇总", "附件清单", "流程记录摘要",
        "创建时间", "更新时间",
        "明细序号",
    ]
    head += [f"明细-{label}" for _, label in LINE_COLS]
    head += [f"收款-{label}" for _, label in PAY_COLS]
    return head


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _subtable_rows(items: Any) -> list[dict]:
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    if isinstance(items, dict):
        return [items]
    return []


def _reg_val(reg: dict, key: str) -> str:
    v = reg.get(key)
    if v is None:
        return ""
    if isinstance(v, dict):
        return str(v.get("name") or v.get("label") or v.get("real_name") or v)
    if isinstance(v, list):
        return "、".join(_reg_val({"x": x}, "x") if isinstance(x, dict) else str(x) for x in v)
    return str(v)


def _map_cn(val: Any, mapping: dict[str, str]) -> str:
    if val is None or val == "":
        return ""
    return mapping.get(str(val).strip(), str(val))


def _source_label(c: dict) -> str:
    ext = (c.get("external_key") or "").strip()
    if ext:
        return "外部推送"
    reg = c.get("registration_json") if isinstance(c.get("registration_json"), dict) else {}
    custom = c.get("custom_fields_json") if isinstance(c.get("custom_fields_json"), dict) else {}
    if (
        reg.get("_external_source") == "jdy"
        or (reg.get("_external_key") or "").strip()
        or custom.get("_src") == "jdy_migration"
        or custom.get("_src_id") is not None
    ):
        return "外部推送"
    return "CRM内录"


def _pay_summary(c: dict) -> str:
    lines: list[str] = []
    for i, p in enumerate(_subtable_rows(c.get("payment_terms_json")), 1):
        parts = [
            f"第{i}笔",
            _cell(p.get("due_date")),
            _cell(p.get("kind")),
            f"{_cell(p.get('ratio'))}%" if p.get("ratio") not in (None, "") else "",
            f"{_cell(p.get('amount'))}元" if p.get("amount") not in (None, "") else "",
            f"提醒:{_cell(p.get('remind'))}" if p.get("remind") else "",
            _cell(p.get("note")),
        ]
        lines.append(" ".join(x for x in parts if x))
    return "\n".join(lines)


def _att_summary(c: dict) -> str:
    reg = c.get("registration_json") or {}
    att = reg.get("_attachments") if isinstance(reg, dict) else {}
    if not isinstance(att, dict):
        att = {}
    lines: list[str] = []
    for slot, label in ATT_SLOTS.items():
        files = att.get(slot) or []
        if not isinstance(files, list):
            files = [files] if files else []
        names: list[str] = []
        for f in files:
            if isinstance(f, str):
                names.append(f)
            elif isinstance(f, dict):
                names.append(f.get("name") or f.get("filename") or "")
        if names:
            lines.append(f"【{label}】" + "；".join(n for n in names if n))
    seen: set[tuple[Any, Any]] = set()
    for a in c.get("attachments") or []:
        key = (a.get("biz_type"), a.get("original_name"))
        if key in seen:
            continue
        seen.add(key)
        label = ATT_BIZ_CN.get(a.get("biz_type") or "", a.get("biz_type") or "附件")
        nm = a.get("original_name") or ""
        size = a.get("file_size") or ""
        lines.append(f"【{label}】{nm}" + (f" ({size}B)" if size else ""))
    return "\n".join(lines)


def _wf_summary(c: dict) -> str:
    parts: list[str] = []
    for l in c.get("wf_logs") or []:
        act = _map_cn(l.get("action"), ACTION_CN)
        node = l.get("node_name") or ""
        who = l.get("actor_name") or ""
        op = (l.get("opinion") or "").strip()
        t = l.get("created_at") or ""
        seg = f"{t} {node} {who} {act}".strip()
        if op:
            seg += f"：{op}"
        parts.append(seg)
    return "\n".join(parts)


def _pending_task(c: dict) -> tuple[str, str]:
    pending = [t for t in (c.get("wf_tasks") or []) if t.get("status") in ("pending", "waiting")]
    if not pending:
        return "", ""
    nodes = "；".join(dict.fromkeys(t.get("node_name") or "" for t in pending if t.get("node_name")))
    users = "；".join(dict.fromkeys(t.get("assignee") or "" for t in pending if t.get("assignee")))
    return nodes, users


def _contract_header(c: dict, export_cell: ExportCellFn) -> list[Any]:
    reg = c.get("registration_json") or {}
    if not isinstance(reg, dict):
        reg = {}
    pend_node, pend_user = _pending_task(c)
    amt = c.get("amount_total")
    if amt is not None:
        amt = export_cell("amount_total", amt)
    return [
        _source_label(c),
        c.get("serial_no") or "",
        export_cell("created_by_name", c.get("created_by_name") or ""),
        c.get("card_date") or "",
        _reg_val(reg, "customer_code") or c.get("customer_code") or "",
        export_cell("customer_name", c.get("customer_name") or ""),
        export_cell("department_name", c.get("department_name") or ""),
        export_cell("assignee_name", c.get("assignee_name") or ""),
        _map_cn(c.get("status"), STATUS_CN),
        _map_cn(c.get("change_type"), CHANGE_TYPE_CN),
        export_cell("acquire_method", c.get("acquire_method") or ""),
        c.get("contract_no") or "",
        c.get("drawing_no") or "",
        c.get("peer_contract_no") or "",
        amt if amt is not None else "",
        c.get("order_date") or "",
        c.get("signed_date") or "",
        c.get("delivery_date") or "",
        c.get("end_date") or "",
    ] + [_reg_val(reg, k) for k, _ in REG_FIELDS] + [
        _map_cn(c.get("version_status"), STATUS_CN),
        _map_cn(c.get("wf_status"), STATUS_CN),
        pend_node,
        pend_user,
        _pay_summary(c),
        _att_summary(c),
        _wf_summary(c),
        c.get("created_at") or "",
        c.get("updated_at") or "",
    ]


def build_flat_export_rows(
    contracts: list[dict],
    export_cell: ExportCellFn | None = None,
) -> list[list[Any]]:
    cell = export_cell or (lambda _fid, v: v)
    headers_len = len(flat_export_headers())
    n_pay = len(PAY_COLS)
    rows: list[list[Any]] = []

    for c in contracts:
        header = _contract_header(c, cell)
        lines_raw = _subtable_rows(c.get("key_clauses_json"))
        pays = _subtable_rows(c.get("payment_terms_json"))
        line_count = len(lines_raw)
        lines = lines_raw if line_count else [{}]
        max_rows = max(line_count, len(pays), 1)

        for idx in range(max_rows):
            line = lines[idx] if idx < len(lines) else {}
            pay = pays[idx] if idx < len(pays) else {}
            row = list(header)
            row.append(str(idx + 1) if idx < line_count else "")
            row += [_cell(line.get(k)) for k, _ in LINE_COLS]
            if idx < len(pays):
                row += [_cell(pay.get(k)) for k, _ in PAY_COLS]
            else:
                row += [""] * n_pay
            if len(row) != headers_len:
                raise ValueError(f"export row width {len(row)} != headers {headers_len}")
            rows.append(row)
    return rows


async def enrich_contracts_for_flat_export(
    db: AsyncSession,
    tenant_id: str,
    rows: list[dict],
    contracts: list[Contract],
) -> list[dict]:
    """补齐单表全览导出所需的版本、流程、附件等字段。"""
    if not rows or not contracts:
        return rows

    by_id = {c.id: c for c in contracts}
    ids = list(by_id.keys())

    ver_rows = (await db.execute(
        select(
            ContractVersion.contract_id,
            ContractVersion.version_no,
            ContractVersion.id,
            ContractVersion.status,
            ContractVersion.key_clauses_json,
        ).where(
            ContractVersion.tenant_id == tenant_id,
            ContractVersion.contract_id.in_(ids),
        )
    )).all()
    ver_map = {
        (cid, vno): {"id": vid, "status": st, "key_clauses_json": clauses}
        for cid, vno, vid, st, clauses in ver_rows
    }

    version_ids = [v["id"] for v in ver_map.values() if v.get("id")]
    wf_by_version: dict[str, dict] = {}
    if version_ids:
        for r in (await db.execute(text("""
            SELECT DISTINCT ON (biz_id)
                   biz_id, id::text AS wf_id, status AS wf_status,
                   started_at::text AS wf_started_at,
                   completed_at::text AS wf_completed_at
            FROM wf_process_instance
            WHERE tenant_id = :t
              AND biz_type = 'contract_version'
              AND biz_id = ANY(:ids)
              AND status NOT IN ('terminated', 'withdrawn', 'rejected')
            ORDER BY biz_id, started_at DESC NULLS LAST
        """), {"t": tenant_id, "ids": version_ids})).mappings().all():
            wf_by_version[str(r["biz_id"])] = dict(r)

    wf_ids = [w["wf_id"] for w in wf_by_version.values() if w.get("wf_id")]
    wf_nodes: dict[str, list] = {}
    wf_tasks: dict[str, list] = {}
    wf_logs: dict[str, list] = {}
    if wf_ids:
        for r in (await db.execute(text("""
            SELECT process_instance_id::text AS pid, node_def_id, node_name, status,
                   started_at::text AS started_at, completed_at::text AS completed_at
            FROM wf_node_instance
            WHERE process_instance_id = ANY(:ids)
            ORDER BY started_at NULLS LAST, id
        """), {"ids": wf_ids})).mappings().all():
            wf_nodes.setdefault(r["pid"], []).append(dict(r))
        for r in (await db.execute(text("""
            SELECT t.process_instance_id::text AS pid, ni.node_name, t.status,
                   u.real_name AS assignee,
                   t.created_at::text AS created_at, t.action_at::text AS action_at
            FROM wf_task_instance t
            JOIN wf_node_instance ni ON ni.id = t.node_instance_id
            LEFT JOIN users u ON u.id = t.assignee_id
            WHERE t.process_instance_id = ANY(:ids)
            ORDER BY t.created_at
        """), {"ids": wf_ids})).mappings().all():
            wf_tasks.setdefault(r["pid"], []).append(dict(r))
        for r in (await db.execute(text("""
            SELECT l.process_instance_id::text AS pid, l.action, l.actor_name, l.opinion,
                   ni.node_name, l.created_at::text AS created_at
            FROM wf_task_action_log l
            LEFT JOIN wf_node_instance ni ON ni.id = l.node_instance_id
            WHERE l.process_instance_id = ANY(:ids)
            ORDER BY l.created_at
        """), {"ids": wf_ids})).mappings().all():
            wf_logs.setdefault(r["pid"], []).append(dict(r))

    att_map: dict[str, list] = {}
    for r in (await db.execute(text("""
        SELECT al.biz_id::text AS cid, al.biz_type, a.original_name, a.content_type,
               a.file_size::text AS file_size, a.uploader_name,
               a.created_at::text AS uploaded_at
        FROM attachment_links al
        JOIN attachments a ON a.id = al.attachment_id
        WHERE al.tenant_id = :t
          AND al.biz_id = ANY(:ids)
          AND (al.biz_type = 'contract' OR al.biz_type LIKE 'contract_%')
        ORDER BY al.biz_type, a.created_at
    """), {"t": tenant_id, "ids": ids})).mappings().all():
        att_map.setdefault(r["cid"], []).append(dict(r))

    from app.domains.customer.models import Customer

    cust_ids = [c.customer_id for c in contracts if c.customer_id]
    cust_codes: dict[str, str] = {}
    if cust_ids:
        for cid, code in (await db.execute(
            select(Customer.id, Customer.customer_code).where(
                Customer.tenant_id == tenant_id,
                Customer.id.in_(cust_ids),
            )
        )).all():
            if code:
                cust_codes[cid] = code

    for d in rows:
        c = by_id.get(d.get("id"))
        if not c:
            continue
        d["external_key"] = c.external_key
        d["custom_fields_json"] = c.custom_fields_json or {}
        if c.customer_id and c.customer_id in cust_codes:
            d["customer_code"] = cust_codes[c.customer_id]
        ver = ver_map.get((c.id, c.current_version_no)) or {}
        d["version_status"] = ver.get("status")
        d["key_clauses_json"] = ver.get("key_clauses_json")
        vid = ver.get("id")
        wf = wf_by_version.get(str(vid)) if vid else None
        if wf:
            d["wf_status"] = wf.get("wf_status")
            pid = wf.get("wf_id")
            d["wf_nodes"] = wf_nodes.get(pid, [])
            d["wf_tasks"] = wf_tasks.get(pid, [])
            d["wf_logs"] = wf_logs.get(pid, [])
        else:
            d["wf_status"] = None
            d["wf_nodes"] = []
            d["wf_tasks"] = []
            d["wf_logs"] = []
        d["attachments"] = att_map.get(c.id, [])
    return rows
