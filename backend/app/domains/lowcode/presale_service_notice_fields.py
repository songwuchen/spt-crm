"""售前服务通知：字段运行时补丁（与生成器 / ensure 共用）。"""


def apply_presale_service_notice_fields(fields: list[dict]) -> None:
    """服务时间等业务日期：简道云为 datetime，CRM 仅选到日。"""
    for fd in fields:
        if not isinstance(fd, dict):
            continue
        if fd.get("id") == "service_time":
            fd["type"] = "date"
            props = dict(fd.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            fd["props"] = props
