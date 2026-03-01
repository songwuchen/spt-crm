from typing import TypeVar, Generic, Optional, List
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None
    traceId: Optional[str] = None


class PageRequest(BaseModel):
    pageNo: int = 1
    pageSize: int = 20


class PageData(BaseModel, Generic[T]):
    items: List[T]
    total: int
    pageNo: int
    pageSize: int


def ok(data=None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def fail(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}
