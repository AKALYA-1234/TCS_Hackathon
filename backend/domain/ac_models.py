"""
Additive Database Models for PS 3.2: AI-Powered AC Optimization
Covers: rooms, ac_units, ac_telemetry, occupancy_readings, schedules, weather,
tariffs, baseline_pred, waste_events, forecasts, proposals, commands,
command_acks, savings_verified, audit_log, ground_truth_labels.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, JSON, Text, ForeignKey, Index
)
from common.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class RoomModel(Base):
    __tablename__ = "rooms"

    id = Column(String(50), primary_key=True)  # e.g., "room-eng-101"
    building = Column(String(100), nullable=False, index=True)  # e.g., "Engineering Hall"
    name = Column(String(100), nullable=False)  # e.g., "Lecture Hall 101"
    room_type = Column(String(50), nullable=False)  # "lecture_hall", "lab", "office", "seminar"
    area_sqm = Column(Float, nullable=False, default=50.0)
    capacity = Column(Integer, nullable=False, default=40)
    target_temp_c = Column(Float, nullable=False, default=24.0)
    min_temp_c = Column(Float, nullable=False, default=23.0)
    max_temp_c = Column(Float, nullable=False, default=26.0)
    is_critical = Column(Boolean, default=False)  # labs/server rooms with strict ranges
    manual_override_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ACUnitModel(Base):
    __tablename__ = "ac_units"

    id = Column(String(50), primary_key=True)  # e.g., "ac-eng-101-a"
    room_id = Column(String(50), ForeignKey("rooms.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    rated_kw = Column(Float, nullable=False, default=5.0)
    cop = Column(Float, default=3.2)  # Coefficient of Performance
    current_status = Column(String(20), default="OFF")  # "ON", "OFF"
    current_set_temp_c = Column(Float, default=24.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ACTelemetryModel(Base):
    __tablename__ = "ac_telemetry"

    # TimescaleDB hypertable partition key: timestamp
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), nullable=False, index=True)
    ac_unit_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True, default=utc_now)
    power_kw = Column(Float, nullable=False, default=0.0)
    set_temp_c = Column(Float, nullable=False, default=24.0)
    room_temp_c = Column(Float, nullable=False, default=25.0)
    outdoor_temp_c = Column(Float, nullable=True, default=32.0)
    occupancy = Column(Integer, nullable=False, default=0)
    expected_occupancy = Column(Integer, nullable=True, default=0)
    on_off_status = Column(String(10), nullable=False, default="OFF")  # "ON", "OFF"
    scheduled_hours = Column(Boolean, nullable=False, default=False)
    baseline_kw = Column(Float, nullable=True, default=0.0)
    baseline_lower_kw = Column(Float, nullable=True, default=0.0)
    baseline_upper_kw = Column(Float, nullable=True, default=0.0)
    wasted_power_kw = Column(Float, nullable=True, default=0.0)
    wasted_kwh = Column(Float, nullable=True, default=0.0)
    wasted_cost_inr = Column(Float, nullable=True, default=0.0)
    is_waste = Column(Boolean, nullable=True, default=False)
    waste_type = Column(String(50), nullable=True)
    state = Column(String(20), nullable=True, default="OFF")

    __table_args__ = (
        Index("idx_ac_telemetry_room_ts", "room_id", "timestamp"),
        Index("idx_ac_telemetry_unit_ts", "ac_unit_id", "timestamp"),
    )


class OccupancyModel(Base):
    __tablename__ = "occupancy_readings"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True, default=utc_now)
    headcount = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, default=0.92)  # Simulated noisy CV estimation confidence
    is_synthetic = Column(Boolean, default=True)


class ScheduleModel(Base):
    __tablename__ = "schedules"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), ForeignKey("rooms.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(String(8), nullable=False)  # "09:00:00"
    end_time = Column(String(8), nullable=False)  # "11:00:00"
    activity_name = Column(String(100), default="Lecture")
    expected_headcount = Column(Integer, default=30)
    enrollment = Column(Integer, default=35)
    
    # Additive fields for rich manual schedule control (backward compatible with defaults)
    setpoint_c = Column(Float, nullable=True, default=24.0)
    precool_mode = Column(String(20), default="auto")  # "auto" (from optimizer) or "manual"
    precool_lead_min = Column(Integer, default=20)
    shutoff_mode = Column(String(20), default="auto")  # "auto" (flywheel) or "manual"
    shutoff_lead_min = Column(Integer, default=15)
    auto_off_empty_min = Column(Integer, default=15)  # minutes of zero occupancy before turnoff
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)


class ScheduleExceptionModel(Base):
    """
    Additive Model: Holiday, Exam Period, One-off Seminar, Temporary Hold.
    Scope: specific room_id, building name, or 'ALL' (campus-wide).
    """
    __tablename__ = "schedule_exceptions"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), nullable=True, index=True)  # room ID, or 'ALL', or null for building-wide
    building = Column(String(100), nullable=True, index=True)
    exception_type = Column(String(30), nullable=False)  # "holiday", "exam_period", "one_off", "temporary_hold"
    title = Column(String(150), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    setpoint_c = Column(Float, nullable=True)
    expected_headcount = Column(Integer, nullable=True)
    hold_state = Column(String(10), nullable=True)  # "ON" or "OFF" for temporary holds
    reason = Column(Text, nullable=False)
    created_by = Column(String(100), default="OPERATOR_ADMIN")
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ScheduleVersionModel(Base):
    """
    Additive Model: Immutable schedule versions for auditability and forward-looking versioning.
    Never overwrites the past; records diffs and snapshots.
    """
    __tablename__ = "schedule_versions"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), ForeignKey("rooms.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=False, index=True, default=utc_now)
    author = Column(String(100), nullable=False, default="OPERATOR_ADMIN")
    summary = Column(Text, nullable=False)
    diff_json = Column(JSON, nullable=True)
    snapshot_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class WeatherModel(Base):
    __tablename__ = "weather"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True, default=utc_now)
    outdoor_temp_c = Column(Float, nullable=False)
    relative_humidity = Column(Float, default=55.0)
    solar_irradiance_wm2 = Column(Float, default=450.0)


class TariffModel(Base):
    __tablename__ = "tariffs"

    id = Column(String(50), primary_key=True, default="default-campus-tariff")
    currency = Column(String(10), default="INR")
    base_rate_per_kwh = Column(Float, default=8.50)  # Regular hours INR/kWh
    peak_rate_per_kwh = Column(Float, default=12.50)  # Peak hours 14:00-18:00
    peak_start_hour = Column(Integer, default=14)
    peak_end_hour = Column(Integer, default=18)
    setpoint_savings_pct_per_deg = Column(Float, default=4.0)  # ASSUMPTION: 4% per °C


class BaselinePredModel(Base):
    __tablename__ = "baseline_pred"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), nullable=False, index=True)
    ac_unit_id = Column(String(50), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    baseline_kw = Column(Float, nullable=False)
    lower_bound_kw = Column(Float, nullable=False)
    upper_bound_kw = Column(Float, nullable=False)
    model_version = Column(String(50), default="seasonal_placeholder_v1")
    is_placeholder = Column(Boolean, default=True)


class WasteEventModel(Base):
    __tablename__ = "waste_events"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), nullable=False, index=True)
    ac_unit_id = Column(String(50), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    # after_hours, ghost_cooling, overcooling, early_start, possible_leakage
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    wasted_kwh = Column(Float, nullable=False, default=0.0)
    wasted_cost_inr = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.85)
    resolved = Column(Boolean, default=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ForecastModel(Base):
    __tablename__ = "forecasts"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), nullable=False, index=True)
    forecast_type = Column(String(20), default="weekly")  # "weekly", "monthly"
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    predicted_kwh = Column(Float, nullable=False)
    lower_kwh = Column(Float, nullable=False)
    upper_kwh = Column(Float, nullable=False)
    predicted_cost_inr = Column(Float, nullable=False)
    is_placeholder = Column(Boolean, default=True)


class ProposalModel(Base):
    __tablename__ = "proposals"

    id = Column(String(64), primary_key=True, default=lambda: f"prop-{uuid.uuid4().hex[:8]}")
    room_id = Column(String(50), nullable=False, index=True)
    ac_unit_id = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False)  # "SET_TEMP", "SHUT_OFF", "PRE_COOL", "OPTIMIZE_SCHEDULE"
    target_value = Column(Float, nullable=True)  # e.g., 25.0 °C
    rationale = Column(Text, nullable=False)
    estimated_saving_kwh = Column(Float, nullable=False, default=0.0)
    estimated_saving_inr = Column(Float, nullable=False, default=0.0)
    source = Column(String(50), default="LLM_AGENT")  # "LLM_AGENT" or "OPTIMIZER"
    rule_validation_status = Column(String(20), default="PENDING")  # "PASSED", "REJECTED", "PASSED_WITH_WARNING"
    rule_validation_notes = Column(Text, nullable=True)
    approval_status = Column(String(20), default="PENDING")  # "PENDING", "APPROVED", "REJECTED", "EXPIRED"
    approval_tier = Column(String(30), default="ONE_CLICK")  # "SUGGEST_ONLY", "ONE_CLICK", "AUTO_SCHEDULED"
    approved_by = Column(String(100), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=True)


class CommandModel(Base):
    __tablename__ = "commands"

    id = Column(String(64), primary_key=True, default=lambda: f"cmd-{uuid.uuid4().hex[:8]}")
    proposal_id = Column(String(64), ForeignKey("proposals.id"), nullable=True)
    room_id = Column(String(50), nullable=False, index=True)
    ac_unit_id = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # "SET_TEMP", "SHUT_OFF", "POWER_ON"
    target_value = Column(Float, nullable=True)
    approved_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), default="PUBLISHED")  # "PUBLISHED", "ACKNOWLEDGED", "EXPIRED", "FAILED"
    ack_received_at = Column(DateTime(timezone=True), nullable=True)


class CommandAckModel(Base):
    __tablename__ = "command_acks"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    command_id = Column(String(64), ForeignKey("commands.id"), nullable=False, index=True)
    ac_unit_id = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # "APPLIED", "REJECTED_EXPIRED", "ERROR"
    reported_temp_c = Column(Float, nullable=True)
    reported_on_off = Column(String(10), nullable=True)
    details = Column(JSON, nullable=True)
    received_at = Column(DateTime(timezone=True), default=utc_now)


class SavingsVerifiedModel(Base):
    __tablename__ = "savings_verified"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    proposal_id = Column(String(64), ForeignKey("proposals.id"), nullable=True)
    room_id = Column(String(50), nullable=False, index=True)
    measured_start = Column(DateTime(timezone=True), nullable=False)
    measured_end = Column(DateTime(timezone=True), nullable=False)
    actual_kwh = Column(Float, nullable=False)
    baseline_kwh = Column(Float, nullable=False)
    savings_kwh_min = Column(Float, nullable=False)  # Reported as a range
    savings_kwh_max = Column(Float, nullable=False)
    savings_kwh_est = Column(Float, nullable=False)
    savings_inr_min = Column(Float, nullable=False)
    savings_inr_max = Column(Float, nullable=False)
    savings_inr_est = Column(Float, nullable=False)
    confidence = Column(Float, default=0.90)
    verified_at = Column(DateTime(timezone=True), default=utc_now)


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)
    actor = Column(String(100), nullable=False)  # "LLM_AGENT", "RULE_ENGINE", "OPERATOR_ADMIN", "SYSTEM"
    event_type = Column(String(50), nullable=False)
    # "PROPOSAL_CREATED", "RULE_VALIDATED", "APPROVED", "REJECTED", "COMMAND_DISPATCHED", "COMMAND_ACKED", "OVERRIDE_ENABLED"
    entity_id = Column(String(64), nullable=True)
    details = Column(JSON, nullable=True)


class GroundTruthLabelModel(Base):
    """
    Ground truth for injected anomalies in the simulator.
    Separated strictly from models and detection algorithms for independent verification.
    """
    __tablename__ = "ground_truth_labels"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String(50), nullable=False, index=True)
    ac_unit_id = Column(String(50), nullable=True)
    anomaly_type = Column(String(50), nullable=False)
    # after_hours, ghost_cooling, overcooling, early_start, possible_leakage
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    severity = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
