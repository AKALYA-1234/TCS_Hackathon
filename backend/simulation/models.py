"""
Scenario Data Models and Schemas for Frostline Scenario Lab
Defines full structure for scenarios, weather curves, occupancy profiles,
disturbances, control modes, and step-by-step simulation results.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class WeatherEvent(BaseModel):
    name: str = "Weather Spike"
    event_type: str = "temp_spike"  # temp_spike, sudden_rain, cloud_cover
    start_hour: float = 13.0
    end_hour: float = 16.0
    delta_temp_c: float = 5.0
    delta_humidity_pct: float = 0.0


class WeatherProfile(BaseModel):
    preset: str = "typical"  # typical, heatwave, cloudy_humid, monsoon, cool_morning, custom
    source: str = "synthetic"  # synthetic, replay, forecast
    hourly_temp: List[float] = Field(default_factory=lambda: [
        23.2, 22.8, 22.5, 22.4, 23.0, 24.2, 26.0, 28.5,
        30.8, 32.5, 33.8, 34.6, 35.0, 34.8, 34.2, 33.1,
        31.5, 29.8, 28.2, 27.0, 26.1, 25.2, 24.5, 23.8
    ])
    hourly_humidity: List[float] = Field(default_factory=lambda: [
        78.0, 80.0, 82.0, 83.0, 80.0, 75.0, 68.0, 62.0,
        55.0, 50.0, 48.0, 46.0, 45.0, 46.0, 49.0, 53.0,
        58.0, 64.0, 68.0, 72.0, 74.0, 75.0, 76.0, 77.0
    ])
    hourly_solar: List[float] = Field(default_factory=lambda: [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.3, 0.6,
        0.8, 0.95, 1.0, 1.0, 0.95, 0.85, 0.7, 0.5,
        0.3, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    ])
    hourly_wind: List[float] = Field(default_factory=lambda: [
        2.1, 1.8, 1.6, 1.5, 1.8, 2.2, 2.8, 3.5,
        4.1, 4.8, 5.2, 5.5, 5.4, 5.0, 4.6, 4.2,
        3.8, 3.2, 2.8, 2.5, 2.4, 2.2, 2.2, 2.0
    ])
    events: List[WeatherEvent] = Field(default_factory=list)


class OccupancyEvent(BaseModel):
    name: str = "Special Seminar"
    room_id: str = "eng-101"
    event_type: str = "seminar"  # seminar, exam_overrun, adhoc_meeting, evacuation, empty_waste
    start_hour: float = 14.0
    end_hour: float = 16.0
    headcount: int = 35


class OccupancyProfile(BaseModel):
    default_mode: str = "timetable"  # timetable, constant, custom_curve
    attendance_pct: float = 85.0
    variation_level: float = 0.15
    events: List[OccupancyEvent] = Field(default_factory=list)
    custom_curves: Dict[str, List[int]] = Field(default_factory=dict)


class RoomDisturbance(BaseModel):
    room_id: str
    disturbance_type: str  # door_open, extra_heat_load, temp_jump, setpoint_change
    start_hour: float
    end_hour: float
    magnitude: float  # extra kW heat, or delta degrees


class ScheduleBlock(BaseModel):
    id: str
    room_id: str
    title: str = "Class Session"
    start_hour: float = 9.0
    end_hour: float = 17.0
    setpoint_c: float = 24.0
    precool_enabled: bool = True


class FaultInjection(BaseModel):
    room_id: str
    fault_type: str  # after_hours, ghost_cooling, overcooling, early_start, possible_leakage
    start_hour: float = 13.0
    duration_hours: float = 2.0
    severity: float = 1.0


class DecoyInjection(BaseModel):
    room_id: str
    decoy_type: str  # late_lab_exception, exam_overrun, adhoc_seminar
    start_hour: float = 18.0
    duration_hours: float = 2.5
    expected_headcount: int = 20


class TariffConfig(BaseModel):
    standard_rate: float = 8.50
    peak_rate: float = 10.50
    peak_start_hour: float = 18.0
    peak_end_hour: float = 22.0


class ScenarioDefinition(BaseModel):
    id: Optional[str] = None
    name: str = "Baseline Campus Day"
    description: str = "Standard 24-hour campus baseline scenario with academic schedules"
    seed: int = 42
    start_time: str = "00:00:00"
    duration_hours: int = 24
    step_minutes: int = 5
    scope: str = "all"  # all, single, building
    selected_rooms: List[str] = Field(default_factory=lambda: [
        "eng-101", "eng-102", "eng-server", "sci-201",
        "sci-202", "adm-301", "adm-302", "lib-401"
    ])
    weather: WeatherProfile = Field(default_factory=WeatherProfile)
    occupancy: OccupancyProfile = Field(default_factory=OccupancyProfile)
    disturbances: List[RoomDisturbance] = Field(default_factory=list)
    schedules: List[ScheduleBlock] = Field(default_factory=list)
    is_holiday: bool = False
    control_modes: List[str] = Field(default_factory=lambda: [
        "no_control", "manual_schedule", "optimizer", "optimizer_auto_off"
    ])
    approval_policy: str = "auto_approve_rule_passed"  # auto_approve_all, auto_approve_rule_passed, reject_all, manual_step
    faults: List[FaultInjection] = Field(default_factory=list)
    decoys: List[DecoyInjection] = Field(default_factory=list)
    tariff: TariffConfig = Field(default_factory=TariffConfig)
    created_at: Optional[str] = None


class StepOutput(BaseModel):
    step_index: int
    time_str: str
    hour: float
    outdoor_temp_c: float
    outdoor_humidity_pct: float
    solar_factor: float
    tariff_rate: float
    is_peak_tariff: bool
    campus_power_kw: float
    campus_baseline_kw: float
    campus_running_kwh: float
    campus_running_inr: float
    rooms: Dict[str, Dict[str, Any]]


class ModeEvaluationResult(BaseModel):
    mode: str
    mode_label: str
    total_energy_kwh: float
    peak_demand_kw: float
    peak_demand_time: str
    total_cost_inr: float
    peak_tariff_cost_inr: float
    energy_saved_vs_no_control_kwh: float
    cost_saved_vs_no_control_inr: float
    energy_saved_vs_baseline_kwh: float
    comfort_violation_minutes: int
    worst_comfort_deviation_c: float
    waste_kwh_breakdown: Dict[str, float]
    proposals_created: int
    proposals_approved: int
    proposals_rejected: int
    rule_blocks_count: int
    anomalies_detected: int
    classifier_tp: int
    classifier_fp: int
    classifier_fn: int
    classifier_precision: float
    classifier_recall: float
    classifier_f1: float
    decoy_false_positives: int
    savings_waterfall: Dict[str, float]  # precool_kwh, shutoff_kwh, setpoint_relax_kwh, auto_off_kwh
    room_kpis: Dict[str, Dict[str, Any]]
    timeline_steps: List[StepOutput] = Field(default_factory=list)


class ScenarioRunResult(BaseModel):
    run_id: str
    scenario_id: Optional[str] = None
    scenario_name: str
    seed: int
    engine_version: str = "2.4.0-sandboxed"
    state_hash: str
    wall_clock_ms: float
    total_steps: int
    step_minutes: int
    duration_hours: int
    modes: Dict[str, ModeEvaluationResult]
    comparison_summary: Dict[str, Any]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
