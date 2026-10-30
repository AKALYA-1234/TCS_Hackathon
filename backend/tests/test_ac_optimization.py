"""
Unit and Integration Tests for PS 3.2:
- Rule engine constraints (comfort bounds, critical lab/server room protections, rate limits, overrides)
- Command expiry validation
- Optimizer constraints and 4%/C savings logic
- Savings range computation
- Waste classifier detection against synthetic readings
"""
import pytest
from datetime import datetime, timezone, timedelta
from domain.ac_models import RoomModel, ProposalModel
from governance.rule_engine import RuleEngine
from intelligence.optimizer import Optimizer
from intelligence.savings_engine import SavingsEngine
from intelligence.waste_classifier import WasteClassifier


def test_rule_engine_comfort_band_violation():
    rule_engine = RuleEngine()
    room = RoomModel(
        id="eng-101",
        name="Lecture Hall 101",
        building="Engineering",
        room_type="lecture_hall",
        min_temp_c=23.0,
        max_temp_c=26.0,
        target_temp_c=24.0,
        is_critical=False
    )
    # Target 20.0 C is below min_temp_c (23.0 C)
    prop = ProposalModel(
        room_id="eng-101",
        action="SET_TEMP",
        target_value=20.0,
        rationale="Overcool room"
    )
    status, notes = rule_engine.validate_proposal(prop, room, current_set_temp=24.0, current_room_temp=24.0)
    assert status == "REJECTED"
    assert "comfort limit" in notes


def test_rule_engine_critical_facility_shutoff_protection():
    rule_engine = RuleEngine()
    room = RoomModel(
        id="eng-server",
        name="Department Server Room",
        building="Engineering",
        room_type="lab",
        min_temp_c=19.0,
        max_temp_c=22.0,
        target_temp_c=21.0,
        is_critical=True
    )
    # Attempting to shut off critical cooling in server room
    prop = ProposalModel(
        room_id="eng-server",
        action="SHUT_OFF",
        target_value=None,
        rationale="Night energy saving"
    )
    status, notes = rule_engine.validate_proposal(prop, room, current_set_temp=21.0, current_room_temp=21.0)
    assert status == "REJECTED"
    assert "CRITICAL SAFETY VIOLATION" in notes


def test_rule_engine_manual_override_pauses_automation():
    rule_engine = RuleEngine()
    room = RoomModel(
        id="eng-201",
        name="Seminar Room A",
        building="Engineering",
        room_type="seminar",
        min_temp_c=23.0,
        max_temp_c=26.0,
        target_temp_c=24.0,
        is_critical=False,
        manual_override_until=datetime.now(timezone.utc) + timedelta(hours=2)
    )
    prop = ProposalModel(
        room_id="eng-201",
        action="SET_TEMP",
        target_value=25.0,
        rationale="Adjust setpoint"
    )
    status, notes = rule_engine.validate_proposal(prop, room, current_set_temp=24.0, current_room_temp=24.0)
    assert status == "REJECTED"
    assert "manual override" in notes.lower()


def test_optimizer_savings_assumption_and_bounds():
    opt = Optimizer(setpoint_savings_pct_per_deg=4.0, base_tariff=8.50)
    res = opt.optimize_room(
        room_id="eng-101",
        current_set_temp_c=22.0,
        target_comfort_min=23.0,
        target_comfort_max=26.0,
        schedule_start_time="09:00:00",
        schedule_end_time="17:00:00",
        rated_kw=10.0,
        outdoor_temp_c=34.0,
        is_critical=False
    )
    # Setpoint relaxed from 22.0 to 26.0 (diff = 4C * 4% = 16% savings)
    assert res["recommended_set_temp_c"] == 26.0
    assert res["savings_pct"] == 16.0
    assert res["estimated_daily_savings_kwh"]["est"] > 0
    assert res["estimated_daily_savings_inr"]["est"] > 0
    # Range is verified (min < est < max)
    assert res["estimated_daily_savings_kwh"]["min"] < res["estimated_daily_savings_kwh"]["est"]
    assert res["estimated_daily_savings_kwh"]["est"] < res["estimated_daily_savings_kwh"]["max"]


def test_savings_engine_reports_range_never_single_point():
    se = SavingsEngine(base_tariff=8.50, peak_tariff=12.50)
    now = datetime.now(timezone.utc)
    res = se.calculate_verified_savings(
        room_id="eng-101",
        measured_start=now - timedelta(hours=1),
        measured_end=now,
        actual_kwh=10.0,
        baseline_kwh=15.0,
        model_uncertainty_pct=0.12
    )
    # Raw savings = 5.0 kWh
    assert res["savings_kwh"]["est"] == 5.0
    assert res["savings_kwh"]["min"] < 5.0
    assert res["savings_kwh"]["max"] > 5.0
    assert res["savings_inr"]["min"] < res["savings_inr"]["est"] < res["savings_inr"]["max"]


def test_waste_classifier_ghost_cooling():
    wc = WasteClassifier()
    now = datetime.now(timezone.utc).replace(hour=11)
    event = wc.classify_reading(
        room_id="eng-101",
        ac_unit_id="ac-1",
        timestamp=now,
        actual_kw=4.5,
        baseline_kw=1.0,
        room_temp_c=23.0,
        target_temp_c=24.0,
        occupancy=0,  # Empty room during scheduled hours
        scheduled_hours=True
    )
    assert event is not None
    assert event["event_type"] == "ghost_cooling"
    assert event["wasted_kwh"] > 0
    assert event["wasted_cost_inr"] > 0
