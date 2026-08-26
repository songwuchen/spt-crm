"""节点操作配置（对齐简道云「节点操作」）。"""
from __future__ import annotations

DEFAULT_NODE_ACTIONS: dict[str, bool] = {
    "submit": True,
    "return": True,
    "reject": False,
    "submit_print": False,
    "save": True,
    "transfer": True,
    "batch_submit": False,
    "signature": False,
}

_LEAD_BIZ_TYPES = frozenset({"lead", "lead_reactivation"})

# 图纸类表单：指派节点通过时打开领用/安装图打印（对齐 schemePrint.isDrawingApproveAndPrintNode）
_DRAWING_PRINT_FORM_CODES = frozenset({
    "drawing_requisition",
    "install_drawing_notice",
    "scheme_management",
    "cs_drawing_request",
})

_DRAWING_PRINT_NODE_NAMES = frozenset({
    "研究院安排",
    "设计指派安排",
    "设计指派安排*",
})


def is_drawing_approve_and_print_node(node_name: str | None) -> bool:
    name = (node_name or "").strip()
    return name in _DRAWING_PRINT_NODE_NAMES or name.startswith("部门指派")


def apply_drawing_print_node_actions(nodes: list | None) -> bool:
    """流程发布/兜底拓扑：图纸类指派节点开启 submit_print。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if not is_drawing_approve_and_print_node(n.get("name")):
            continue
        actions = dict(n.get("node_actions") or {})
        if not actions.get("submit_print"):
            actions["submit_print"] = True
            n["node_actions"] = actions
            changed = True
    return changed


def _implicit_submit_print(
    node: dict | None,
    *,
    biz_type: str | None = None,
    form_code: str | None = None,
) -> bool:
    code = form_code or biz_type or ""
    if code not in _DRAWING_PRINT_FORM_CODES:
        return False
    return is_drawing_approve_and_print_node((node or {}).get("name"))


def parse_node_actions(
    node: dict | None,
    *,
    biz_type: str | None = None,
    form_code: str | None = None,
) -> dict[str, bool]:
    raw = (node or {}).get("node_actions")
    out = dict(DEFAULT_NODE_ACTIONS)
    if isinstance(raw, dict):
        for k in DEFAULT_NODE_ACTIONS:
            if k in raw and isinstance(raw[k], bool):
                out[k] = raw[k]
    if (biz_type or "") in _LEAD_BIZ_TYPES:
        if not isinstance(raw, dict) or raw.get("reject") is not False:
            out["reject"] = True
    if _implicit_submit_print(node, biz_type=biz_type, form_code=form_code):
        out["submit_print"] = True
    return out


def node_action_allowed(
    node: dict | None,
    action: str,
    *,
    biz_type: str | None = None,
    form_code: str | None = None,
) -> bool:
    """action: submit / return / reject / submit_print / save / transfer / batch_submit / signature"""
    return parse_node_actions(node, biz_type=biz_type, form_code=form_code).get(
        action, DEFAULT_NODE_ACTIONS.get(action, True),
    )
