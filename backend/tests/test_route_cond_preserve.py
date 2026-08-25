"""设计器保存：非互斥连线条件失效时保留拓扑。"""
from app.domains.lowcode.jdy_id_remap import (
    clean_unknown_dept_ids_in_routes,
    clean_unknown_person_ids_in_routes,
)


def test_preserve_non_exclusive_route_when_dept_condition_invalid():
    routes = [{
        "id": "r_custom",
        "source": "n_sales",
        "target": "n_clerk_verify",
        "condition": {
            "rel": "and",
            "cond": [{"field": "department", "operator": "eq", "value": "bad-dept-id"}],
        },
    }]
    kept, stats = clean_unknown_dept_ids_in_routes(
        routes, valid_dept_ids={"real-dept"},
        preserve_routes_without_exclusive=True,
    )
    assert len(kept) == 1
    assert kept[0]["source"] == "n_sales"
    assert "condition" not in kept[0]
    assert stats["routes_dropped"] == 0


def test_drop_exclusive_route_when_dept_condition_invalid():
    routes = [{
        "id": "r_ex",
        "source": "n1",
        "target": "n2",
        "exclusive_group": "ex_n1",
        "condition": {
            "field": "department", "operator": "eq", "value": "bad-dept-id",
        },
    }]
    kept, stats = clean_unknown_dept_ids_in_routes(
        routes, valid_dept_ids={"real-dept"},
        preserve_routes_without_exclusive=True,
    )
    assert kept == []
    assert stats["routes_dropped"] == 1


def test_preserve_non_exclusive_when_person_jdy_id_unmapped():
    routes = [{
        "id": "r_fin",
        "source": "n_finance",
        "target": "n_clerk_verify",
        "condition": {
            "field": "salesperson", "operator": "eq", "value": "6603dadbd23d27d4d03d8824",
        },
    }]
    kept, stats = clean_unknown_person_ids_in_routes(
        routes, preserve_routes_without_exclusive=True,
    )
    assert len(kept) == 1
    assert kept[0]["target"] == "n_clerk_verify"
    assert "condition" not in kept[0]
    assert stats["routes_dropped"] == 0
