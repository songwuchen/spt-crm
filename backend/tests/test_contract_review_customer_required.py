import pytest

from app.common.exceptions import BusinessException
from app.domains.contract_review.service import _require_customer_id


def test_require_customer_id_rejects_empty():
    with pytest.raises(BusinessException) as exc:
        _require_customer_id(None)
    assert exc.value.message == "请选择关联客户"

    with pytest.raises(BusinessException):
        _require_customer_id("   ")


def test_require_customer_id_accepts_value():
    _require_customer_id("cust-1")
