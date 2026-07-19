"""规则引擎前后端一致性用例（后端侧）。

与 frontend/src/components/lowcode/__tests__/ruleEngineParity.test.ts 读同一份
shared/form_rule_parity_cases.json。两边都跑一遍同样的用例，任何一侧的语义漂移都会
在这里暴露 —— 漂移的后果是「前端隐藏了该字段、后端仍报它必填」这类用户无法自救的死锁。
"""
import json
from pathlib import Path

import pytest

from app.domains.lowcode.rule_engine import (
    compute_field_states,
    evaluate_condition,
    validate_required_with_rules,
)

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "shared" / "form_rule_parity_cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES["states"], ids=lambda c: c["name"])
def test_field_states_parity(case):
    states = compute_field_states(
        case["fields"], case.get("values") or {}, case.get("rules") or [], case.get("permissions"),
    )
    for field_id, expected in case["expect"].items():
        for key, want in expected.items():
            assert states[field_id][key] is want, f"{case['name']}: {field_id}.{key}"


@pytest.mark.parametrize("case", CASES["required"], ids=lambda c: c["name"])
def test_required_parity(case):
    err = validate_required_with_rules(
        case["fields"], case.get("values") or {}, case.get("rules") or [], case.get("permissions"),
    )
    assert (err is not None) is case["expectError"], f"{case['name']}: got {err!r}"


@pytest.mark.parametrize(
    "case", CASES["operators"],
    ids=lambda c: f"{c['actual']!r}-{c['operator']}-{c['value']!r}",
)
def test_operator_parity(case):
    cond = {"field": "f", "operator": case["operator"], "value": case["value"]}
    assert evaluate_condition(cond, {"f": case["actual"]}, {}) is case["expect"]
