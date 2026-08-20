"""简道云人员 MongoId 在流程条件中的映射与回显。"""
from app.domains.lowcode.jdy_id_remap import (
    JDY_PERSON_NAMES,
    PERSON_COND_FIELDS,
    jdy_person_id_to_name,
    remap_jdy_person_ids_in_routes,
)


def test_guo_chun_in_jdy_person_names():
    assert JDY_PERSON_NAMES["6603dadbd23d27d4d03d8824"] == "郭椿"


def test_sales_person_in_person_cond_fields():
    assert "sales_person" in PERSON_COND_FIELDS


def test_remap_sales_person_condition():
    routes = [{
        "from": "a",
        "to": "b",
        "condition": {
            "field": "sales_person",
            "operator": "in",
            "value": ["6603dadbd23d27d4d03d8824"],
        },
    }]
    id_map = {"6603dadbd23d27d4d03d8824": "crm-uuid-guo-chun"}
    new_routes, stats = remap_jdy_person_ids_in_routes(routes, id_map)
    assert new_routes[0]["condition"]["value"] == ["crm-uuid-guo-chun"]
    assert stats["replaced"] == 1


def test_jdy_person_id_to_name():
    names = jdy_person_id_to_name()
    assert names["6603dadbd23d27d4d03d8824"] == "郭椿"
