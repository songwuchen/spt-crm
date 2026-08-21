# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.domains.lowcode.workflow_service import (
    apply_shipment_notice_approvers,
    apply_cs_product_replace_approvers,
    apply_cs_product_return_approvers,
    apply_cs_service_delay_approvers,
    apply_cs_correspondence_approvers,
    apply_xunhan_contract_review_approvers,
    apply_prod_card_supplement_approvers,
)


def load_pack(path: Path):
    text = path.read_text(encoding="utf-8")
    prefix, rest = text.split("json.loads(r'''", 1)
    raw, suffix = rest.rsplit("'''", 1)
    return prefix + "json.loads(r'''", json.loads(raw), "'''" + suffix


def save_pack(path: Path, prefix: str, data: dict, suffix: str):
    path.write_text(
        prefix + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + suffix,
        encoding="utf-8",
    )


base = Path(__file__).resolve().parents[1] / "app" / "domains" / "lowcode"

# shipment
p = base / "_shipment_notice_generated.py"
prefix, data, suffix = load_pack(p)
print("shipment", apply_shipment_notice_approvers(data["shipment_notice"]["flow_nodes"]))
save_pack(p, prefix, data, suffix)

# customer service pack
p = base / "_customer_service_jdy_generated.py"
prefix, data, suffix = load_pack(p)
for fk, fn in [
    ("cs_product_replace", apply_cs_product_replace_approvers),
    ("cs_product_return", apply_cs_product_return_approvers),
    ("cs_service_delay", apply_cs_service_delay_approvers),
    ("cs_correspondence", apply_cs_correspondence_approvers),
]:
    print(fk, fn(data[fk]["flow_nodes"]))
save_pack(p, prefix, data, suffix)

# xunhan
p = base / "_xunhan_contract_review_generated.py"
prefix, data, suffix = load_pack(p)
print("xunhan", apply_xunhan_contract_review_approvers(data["xunhan_contract_review"]["flow_nodes"]))
save_pack(p, prefix, data, suffix)

# prod card
p = base / "_prod_card_jdy_generated.py"
prefix, data, suffix = load_pack(p)
print("prod", apply_prod_card_supplement_approvers(data["prod_card_supplement"]["flow_nodes"]))
save_pack(p, prefix, data, suffix)

# verify
checks = [
    (base / "_shipment_notice_generated.py", "shipment_notice", ["n8", "n10", "n27"]),
    (base / "_customer_service_jdy_generated.py", "cs_service_delay", ["n3", "n4", "n7"]),
    (base / "_customer_service_jdy_generated.py", "cs_product_replace", ["n4", "n9", "n16"]),
    (base / "_customer_service_jdy_generated.py", "cs_product_return", ["n3", "n20"]),
    (base / "_customer_service_jdy_generated.py", "cs_correspondence", ["n3"]),
    (base / "_xunhan_contract_review_generated.py", "xunhan_contract_review", ["n3"]),
    (base / "_prod_card_jdy_generated.py", "prod_card_supplement", ["n5", "n45"]),
]
for path, form, ids in checks:
    _, data, _ = load_pack(path)
    for n in data[form]["flow_nodes"]:
        if n.get("id") in ids:
            print("OK", form, n["id"], n["name"], n.get("approver_rule"))
