"""
Simulation Service for Scenario Lab
Manages Scenario Presets, CRUD operations, Sandboxed Execution,
In-memory run caching, and SSE Playback streaming.
"""
import csv
import io
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from simulation.models import (
    ScenarioDefinition, ScenarioRunResult, WeatherProfile, WeatherEvent,
    OccupancyProfile, OccupancyEvent, FaultInjection, DecoyInjection, ScheduleBlock, TariffConfig
)
from simulation.engine import ScenarioRunner, CAMPUS_ROOMS_CATALOG

logger = logging.getLogger("simulation.service")


def get_builtin_presets() -> List[ScenarioDefinition]:
    """Generates rich standard presets for the Scenario Lab."""
    # 1. Normal Day
    normal = ScenarioDefinition(
        id="preset-normal",
        name="Typical Campus Academic Day",
        description="Standard diurnal temperature profile (23-35°C), 85% class attendance, normal timetable.",
        seed=42,
        duration_hours=24,
        step_minutes=5,
        scope="all"
    )

    # 2. Heatwave
    heatwave_temp = [t + 4.5 for t in normal.weather.hourly_temp]  # Peaks at ~39.5°C
    heatwave = ScenarioDefinition(
        id="preset-heatwave",
        name="Severe Summer Heatwave (+4.5°C)",
        description="Extreme ambient heatwave peaking at 39.5°C with severe thermal stress on cooling coils.",
        seed=101,
        duration_hours=24,
        step_minutes=5,
        scope="all",
        weather=WeatherProfile(
            preset="heatwave",
            hourly_temp=heatwave_temp,
            events=[WeatherEvent(name="Peak Afternoon Spike", event_type="temp_spike", start_hour=13.0, end_hour=16.5, delta_temp_c=2.0)]
        )
    )

    # 3. Exam Day
    exam_events = [
        OccupancyEvent(name="Finals Session 1", room_id="sci-202", event_type="exam_overrun", start_hour=9.0, end_hour=13.0, headcount=120),
        OccupancyEvent(name="Finals Session 2", room_id="sci-202", event_type="exam_overrun", start_hour=14.0, end_hour=17.5, headcount=115),
        OccupancyEvent(name="Lab Exam", room_id="eng-101", event_type="exam_overrun", start_hour=9.5, end_hour=13.5, headcount=40)
    ]
    exam = ScenarioDefinition(
        id="preset-exam",
        name="Campus Final Examinations Day",
        description="Full capacity attendance (100%) in lecture halls and laboratories with exam overruns.",
        seed=202,
        duration_hours=24,
        step_minutes=5,
        scope="all",
        occupancy=OccupancyProfile(
            attendance_pct=100.0,
            events=exam_events
        )
    )

    # 4. Holiday
    holiday = ScenarioDefinition(
        id="preset-holiday",
        name="Campus Public Holiday",
        description="Zero scheduled classes. Tests setback enforcement and shutdown of academic zones.",
        seed=303,
        duration_hours=24,
        step_minutes=5,
        scope="all",
        is_holiday=True
    )

    # 5. After-Hours Leak Fault
    fault_leak = ScenarioDefinition(
        id="preset-after-hours",
        name="After-Hours Waste & Ghost Cooling Injections",
        description="Injected ghost cooling in Lab 201 and after-hours overnight running in Seminar Room to test classifier.",
        seed=404,
        duration_hours=24,
        step_minutes=5,
        scope="all",
        faults=[
            FaultInjection(room_id="eng-101", fault_type="ghost_cooling", start_hour=13.0, duration_hours=2.5, severity=1.0),
            FaultInjection(room_id="adm-301", fault_type="after_hours", start_hour=21.0, duration_hours=5.0, severity=1.0)
        ],
        decoys=[
            DecoyInjection(room_id="sci-201", decoy_type="late_lab_exception", start_hour=18.0, duration_hours=3.0, expected_headcount=15)
        ]
    )

    # 6. Server Room Stress
    server_stress = ScenarioDefinition(
        id="preset-server-stress",
        name="Central Server Room Thermal Infiltration Test",
        description="Tests invariant protection on eng-server: server room is never switched off under any control mode.",
        seed=505,
        duration_hours=24,
        step_minutes=5,
        scope="single",
        selected_rooms=["eng-server"],
        weather=WeatherProfile(
            preset="heatwave",
            hourly_temp=[t + 3.0 for t in normal.weather.hourly_temp]
        )
    )

    return [normal, heatwave, exam, holiday, fault_leak, server_stress]


class SimulationService:
    def __init__(self):
        self.scenarios_store: Dict[str, ScenarioDefinition] = {}
        self.runs_store: Dict[str, ScenarioRunResult] = {}
        self._init_presets()

    def _init_presets(self):
        for p in get_builtin_presets():
            self.scenarios_store[p.id] = p

    def list_presets(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "duration_hours": p.duration_hours,
                "scope": p.scope,
                "preset_key": p.weather.preset
            }
            for p in self.scenarios_store.values()
            if p.id.startswith("preset-")
        ]

    def list_scenarios(self) -> List[ScenarioDefinition]:
        return list(self.scenarios_store.values())

    def get_scenario(self, scenario_id: str) -> Optional[ScenarioDefinition]:
        return self.scenarios_store.get(scenario_id)

    def save_scenario(self, scenario: ScenarioDefinition) -> ScenarioDefinition:
        if not scenario.id:
            scenario.id = f"sc-{uuid.uuid4().hex[:8]}"
        scenario.created_at = datetime.now(timezone.utc).isoformat()
        self.scenarios_store[scenario.id] = scenario
        logger.info(f"Saved scenario [{scenario.id}]: {scenario.name}")
        return scenario

    def delete_scenario(self, scenario_id: str) -> bool:
        if scenario_id in self.scenarios_store:
            del self.scenarios_store[scenario_id]
            return True
        return False

    def validate_scenario(self, sc: ScenarioDefinition) -> List[Dict[str, str]]:
        """Validates scenario constraints and returns errors list."""
        errors = []
        if sc.duration_hours not in (1, 6, 24, 72, 168):
            errors.append({"field": "duration_hours", "error": "Duration must be 1, 6, 24, 72 (3d), or 168 (7d) hours."})

        if sc.step_minutes not in (1, 5, 10, 15, 30):
            errors.append({"field": "step_minutes", "error": "Step minutes must be 1, 5, 10, 15, or 30."})

        # Validate selected rooms
        for r in sc.selected_rooms:
            if r not in CAMPUS_ROOMS_CATALOG:
                errors.append({"field": "selected_rooms", "error": f"Unknown room ID: '{r}'"})

        # Exception room safety validation
        for block in sc.schedules:
            if block.room_id == "eng-server" and block.setpoint_c > 24.0:
                errors.append({
                    "field": "schedules",
                    "error": f"Safety Invariant Violation: Server Room eng-server setpoint ({block.setpoint_c}°C) exceeds max critical threshold (24.0°C)."
                })

        return errors

    def execute_run(self, scenario: ScenarioDefinition) -> ScenarioRunResult:
        """Executes a fully sandboxed scenario run."""
        errors = self.validate_scenario(scenario)
        if errors:
            raise ValueError(f"Scenario validation failed: {errors}")

        runner = ScenarioRunner(scenario)
        result = runner.run()
        self.runs_store[result.run_id] = result
        logger.info(f"Executed run [{result.run_id}] in {result.wall_clock_ms}ms (hash: {result.state_hash[:8]})")
        return result

    def get_run(self, run_id: str) -> Optional[ScenarioRunResult]:
        return self.runs_store.get(run_id)

    def export_run_csv(self, run_id: str, mode: str = "optimizer") -> str:
        """Generates CSV text of the timeline steps for a specific control mode."""
        run = self.get_run(run_id)
        if not run or mode not in run.modes:
            return ""

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "step_index", "time", "hour", "outdoor_temp_c", "outdoor_humidity_pct",
            "is_peak_tariff", "tariff_rate_inr", "campus_power_kw", "campus_baseline_kw",
            "campus_running_kwh", "campus_running_inr"
        ])

        mode_res = run.modes[mode]
        for step in mode_res.timeline_steps:
            writer.writerow([
                step.step_index, step.time_str, step.hour, step.outdoor_temp_c,
                step.outdoor_humidity_pct, step.is_peak_tariff, step.tariff_rate,
                step.campus_power_kw, step.campus_baseline_kw,
                step.campus_running_kwh, step.campus_running_inr
            ])

        return output.getvalue()


# Singleton Simulation Service
simulation_service = SimulationService()
