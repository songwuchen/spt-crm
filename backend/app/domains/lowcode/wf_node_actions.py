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


def parse_node_actions(node: dict | None, *, biz_type: str | None = None) -> dict[str, bool]:
    raw = (node or {}).get("node_actions")
    out = dict(DEFAULT_NODE_ACTIONS)
    if isinstance(raw, dict):
        for k in DEFAULT_NODE_ACTIONS:
            if k in raw and isinstance(raw[k], bool):
                out[k] = raw[k]
    if (biz_type or "") in _LEAD_BIZ_TYPES:
        if not isinstance(raw, dict) or raw.get("reject") is not False:
            out["reject"] = True
    return out


def node_action_allowed(
    node: dict | None, action: str, *, biz_type: str | None = None,
) -> bool:
    """action: submit / return / reject / submit_print / save / transfer / batch_submit / signature"""
    return parse_node_actions(node, biz_type=biz_type).get(
        action, DEFAULT_NODE_ACTIONS.get(action, True),
    )
