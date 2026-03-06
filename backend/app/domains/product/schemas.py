from typing import Optional
from pydantic import BaseModel, Field


class ProductCategoryCreate(BaseModel):
    name: str = Field(..., max_length=100)
    parent_id: Optional[str] = None
    sort_order: Optional[int] = 0
    description: Optional[str] = Field(None, max_length=500)


class ProductCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[str] = None
    sort_order: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)


class ProductCreate(BaseModel):
    product_code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    category_id: Optional[str] = None
    item_type: Optional[str] = Field(None, pattern=r"^(standard|nonstandard|service|spare)$")
    spec: Optional[str] = Field(None, max_length=500)
    unit: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[float] = Field(None, ge=0)
    cost_price: Optional[float] = Field(None, ge=0)
    leadtime_days: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = True
    remark: Optional[str] = None


class ProductUpdate(BaseModel):
    product_code: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=200)
    category_id: Optional[str] = None
    item_type: Optional[str] = Field(None, pattern=r"^(standard|nonstandard|service|spare)$")
    spec: Optional[str] = Field(None, max_length=500)
    unit: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[float] = Field(None, ge=0)
    cost_price: Optional[float] = Field(None, ge=0)
    leadtime_days: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    remark: Optional[str] = None
