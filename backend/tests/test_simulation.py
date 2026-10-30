"""
Scenario Lab & Simulation Engine Verification Suite
Tests:
1. Scenario validation (duration hours, step minutes, exception room safety)
2. ISOLATION PROOF: Verifies zero database mutations across live tables
3. DETERMINISM PROOF: Verifies identical state hashes with identical seed
4. PERFORMANCE: Verifies 24h all-rooms run completes in < 15 seconds
5. MULTI-MODE COMPARISON: Optimizer achieves savings vs no_control
6. CRITICAL INVARIANT: Server room never switched off
"""
import pytest
import asyncio
import time
from sqlalchemy import text
from common.database import AsyncSessionLocal

from simulation.models import (
    ScenarioDefinition, WeatherProfile, ScheduleBlock
)
from simulation.engine import ScenarioRunner
from simulation.service import simulation_service


def test_scenario_validation_rules():
    """Validates duration, step minutes, and critical room safety constraints."""
    # Invalid duration
    bad_sc = ScenarioDefinition(duration_hours=12)
    errors = simulation_service.validate_scenario(bad_sc)
    assert any("duration_hours" in e["field"] for e in errors)

    # Invalid server room setpoint violation
    bad_server_sc = ScenarioDefinition(
        schedules=[ScheduleBlock(id="b1", room_id="eng-server", setpoint_c=28.0)]
    )
    errors = simulation_service.validate_scenario(bad_server_sc)
    assert any("eng-server" in e["error"] for e in errors)

    # Valid scenario
    valid_sc = ScenarioDefinition(duration_hours=24, step_minutes=5)
    errors = simulation_service.validate_scenario(valid_sc)
    assert len(errors) == 0


def test_simulation_determinism():
    """Determinism proof: two independent runs with seed=42 yield identical state hashes."""
    sc1 = ScenarioDefinition(seed=42, duration_hours=24)
    res1 = ScenarioRunner(sc1).run()

    sc2 = ScenarioDefinition(seed=42, duration_hours=24)
    res2 = ScenarioRunner(sc2).run()

    assert res1.state_hash == res2.state_hash
    assert res1.modes["optimizer"].total_energy_kwh == res2.modes["optimizer"].total_energy_kwh
    assert res1.modes["optimizer"].total_cost_inr == res2.modes["optimizer"].total_cost_inr


def test_simulation_performance_speed():
    """Performance test: 24h all-rooms simulation must complete in under 15 seconds."""
    sc = ScenarioDefinition(duration_hours=24, step_minutes=5, scope="all")
    start = time.perf_counter()
    runner = ScenarioRunner(sc)
    res = runner.run()
    elapsed_s = time.perf_counter() - start

    assert elapsed_s < 15.0, f"Run took {elapsed_s}s, exceeding 15s limit"
    assert res.total_steps == 288
    assert len(res.modes) == 4


def test_multi_mode_comparison_savings():
    """Validates that optimizer modes achieve measurable energy and cost savings vs no_control."""
    sc = ScenarioDefinition(duration_hours=24, step_minutes=5, scope="all")
    runner = ScenarioRunner(sc)
    res = runner.run()

    no_ctrl = res.modes["no_control"]
    opt = res.modes["optimizer"]

    # Optimizer relaxes setpoint and coasts before class end
    assert opt.total_energy_kwh < no_ctrl.total_energy_kwh
    assert opt.total_cost_inr < no_ctrl.total_cost_inr
    assert opt.energy_saved_vs_no_control_kwh > 0.0
    assert opt.cost_saved_vs_no_control_inr > 0.0


def test_server_room_never_shut_off():
    """Safety Invariant: Central Server Room eng-server is NEVER shut off under any mode."""
    sc = ScenarioDefinition(duration_hours=24, scope="single", selected_rooms=["eng-server"])
    runner = ScenarioRunner(sc)
    res = runner.run()

    for mode_name, mode_eval in res.modes.items():
        for step in mode_eval.timeline_steps:
            server_state = step.rooms["eng-server"]["state"]
            assert server_state in ("cooling", "idle"), f"Server room unexpectedly entered state {server_state} in mode {mode_name}"
            # Power draw is never 0 (must stay running)
            assert step.rooms["eng-server"]["power_kw"] > 1.0


def test_sandboxed_database_isolation():
    """
    ISOLATION PROOF:
    Measures row counts of all live database tables before and after a 24h all-rooms run.
    Must verify delta = 0 across all live tables.
    """
    async def _check():
        tables = ["ac_telemetry", "waste_events", "proposals", "commands"]
        counts_before = {}
        async with AsyncSessionLocal() as session:
            for t in tables:
                r = await session.execute(text(f"SELECT COUNT(*) FROM {t}"))
                counts_before[t] = r.scalar()

        # Execute full 24h all-rooms scenario run
        sc = ScenarioDefinition(duration_hours=24, step_minutes=5, scope="all")
        result = simulation_service.execute_run(sc)
        assert result.run_id is not None

        counts_after = {}
        async with AsyncSessionLocal() as session:
            for t in tables:
                r = await session.execute(text(f"SELECT COUNT(*) FROM {t}"))
                counts_after[t] = r.scalar()

        for t in tables:
            delta = counts_after[t] - counts_before[t]
            assert delta == 0, f"Isolation breach! Table '{t}' changed by {delta} rows."

    asyncio.run(_check())
