from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class MeasurementCreate(BaseModel):
    record_no: Optional[str] = Field(None, max_length=64)
    ticket_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(None, max_length=300)
    service_date: Optional[date] = None
    engineer_id: Optional[str] = None
    engineer_name: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=32)
    equipment_name: Optional[str] = Field(None, max_length=200)
    equipment_model: Optional[str] = Field(None, max_length=120)
    product_no: Optional[str] = Field(None, max_length=120)
    motor_power_kw: Optional[float] = Field(None, ge=0)
    amplitude_mm: Optional[float] = Field(None, ge=0)
    material_name: Optional[str] = Field(None, max_length=120)
    layer_thickness_mm: Optional[float] = Field(None, ge=0)
    feed_size_mm: Optional[float] = Field(None, ge=0)
    screen_efficiency: Optional[float] = Field(None, ge=0, le=100)
    throughput_tph: Optional[float] = Field(None, ge=0)
    source_temp_c: Optional[float] = None
    ambient_temp_c: Optional[float] = None
    running_current_a: Optional[float] = Field(None, ge=0)
    daily_run_hours: Optional[float] = Field(None, ge=0, le=24)
    service_rating: Optional[str] = Field(None, max_length=16)
    product_rating: Optional[str] = Field(None, max_length=16)
    result_desc: Optional[str] = Field(None, max_length=4000)
    issues: Optional[str] = Field(None, max_length=4000)
    remark: Optional[str] = Field(None, max_length=2000)


class MeasurementUpdate(MeasurementCreate):
    pass
