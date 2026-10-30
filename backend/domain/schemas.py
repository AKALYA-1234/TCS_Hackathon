"""
Pydantic Schemas for PS 3.2 AC Usage Optimization API and Services
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RoomBase(BaseModel):
    id: str
    building: str
    name: str
    room_type: str
    area_sqm: float
    capacity: int
    target_temp_c: float = 24.0
    min_temp_c: float = 23.0
    max_temp_c: float = 26.0
    is_critical: bool = False
    manual_override_until: Optional[datetime] = None


class ACUnitBase(BaseModel):
    id: str
    room_id: str
    name: str
    rated_kw: float
    cop: float = 3.2
    current_status: str = "OFF"
    current_set_temp_c: float = 24.0


class ACTelemetryRecord(BaseModel):
    room_id: str
    ac_unit_id: str
    timestamp: datetime
    power_kw: float
    set_temp_c: float
    room_temp_c: float
    outdoor_temp_c: Optional[float] = 32.0
    occupancy: int
    on_off_status: str
    scheduled_hours: bool


class ScheduleItem(BaseModel):
    id: Optional[str] = None
    room_id: str
    day_of_week: int
    start_time: str
    end_time: str
    activity_name: str
    expected_headcount: int
    enrollment: int


class TariffConfig(BaseModel):
    id: str = "default-campus-tariff"
    currency: str = "INR"
    base_rate_per_kwh: float = 8.50
    peak_rate_per_kwh: float = 12.50
    peak_start_hour: int = 14
    peak_end_hour: int = 18
    setpoint_savings_pct_per_deg: float = 4.0


class WasteEventDTO(BaseModel):
    id: str
    room_id: str
    ac_unit_id: Optional[str] = None
    event_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    wasted_kwh: float
    wasted_cost_inr: float
    confidence: float
    resolved: bool = False
    details: Optional[Dict[str, Any]] = None


class ProposalCreate(BaseModel):
    room_id: str
    ac_unit_id: Optional[str] = None
    action: str  # "SET_TEMP", "SHUT_OFF", "PRE_COOL"
    target_value: Optional[float] = None
    rationale: str
    estimated_saving_kwh: float
    estimated_saving_inr: float
    source: str = "LLM_AGENT"


class ProposalDTO(BaseModel):
    id: str
    room_id: str
    ac_unit_id: Optional[str] = None
    action: str
    target_value: Optional[float] = None
    rationale: str
    estimated_saving_kwh: float
    estimated_saving_inr: float
    source: str
    rule_validation_status: str
    rule_validation_notes: Optional[str] = None
    approval_status: str
    approval_tier: str
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None


class CommandDispatch(BaseModel):
    proposal_id: Optional[str] = None
    room_id: str
    ac_unit_id: str
    action: str
    target_value: Optional[float] = None
    approved_by: str = "admin"
    expiry_seconds: int = 300  # Default 5 minutes


class CommandDTO(BaseModel):
    id: str
    proposal_id: Optional[str] = None
    room_id: str
    ac_unit_id: str
    action: str
    target_value: Optional[float] = None
    approved_by: str
    created_at: datetime
    expires_at: datetime
    status: str
    ack_received_at: Optional[datetime] = None


class SavingsVerifiedDTO(BaseModel):
    id: str
    proposal_id: Optional[str] = None
    room_id: str
    measured_start: datetime
    measured_end: datetime
    actual_kwh: float
    baseline_kwh: float
    savings_kwh_min: float
    savings_kwh_max: float
    savings_kwh_est: float
    savings_inr_min: float
    savings_inr_max: float
    savings_inr_est: float
    confidence: float
    verified_at: datetime


class SimulatorControlRequest(BaseModel):
    action: str  # "start", "stop", "reset", "set_speed", "inject_anomaly"
    speed_multiplier: Optional[int] = None  # e.g., 60 = 1s is 1 min
    anomaly_type: Optional[str] = None
    room_id: Optional[str] = None
    duration_minutes: Optional[int] = 30


class ChatRequest(BaseModel):
    message: str
    room_id: Optional[str] = None
