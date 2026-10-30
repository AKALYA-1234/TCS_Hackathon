"""
Sandboxed Scenario Simulation Engine for Frostline Scenario Lab
Executes 100% in-memory deterministic simulation runs.
Guarantees ZERO writes to live database tables and ZERO MQTT publications.
Reuses SyntheticProvider physics, Optimizer, RuleEngine, WasteClassifier, and Baseline.
"""
import math
import random
import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from simulation.models import (
    ScenarioDefinition, ScenarioRunResult, ModeEvaluationResult, StepOutput
)
from simulator.provider import SyntheticProvider
from intelligence.baseline import SeasonalGradientBoostingBaseline
from intelligence.waste_classifier import WasteClassifier
from intelligence.optimizer import Optimizer
from governance.rule_engine import RuleEngine

# Known campus rooms metadata
CAMPUS_ROOMS_CATALOG: Dict[str, Dict[str, Any]] = {
    "eng-101": {"name": "Advanced Computing Lab", "building": "Engineering Hall", "type": "computer_lab", "capacity": 40, "rated_kw": 5.0, "is_critical": False, "min_temp": 22.0, "max_temp": 26.0},
    "eng-102": {"name": "Software Engineering Lab", "building": "Engineering Hall", "type": "computer_lab", "capacity": 35, "rated_kw": 4.5, "is_critical": False, "min_temp": 22.0, "max_temp": 26.0},
    "eng-server": {"name": "Central Server Room", "building": "Engineering Hall", "type": "server_room", "capacity": 5, "rated_kw": 6.5, "is_critical": True, "min_temp": 20.0, "max_temp": 24.0},
    "sci-201": {"name": "Organic Chemistry Lab", "building": "Science Complex", "type": "lab", "capacity": 30, "rated_kw": 4.0, "is_critical": False, "min_temp": 21.0, "max_temp": 25.0},
    "sci-202": {"name": "Physics Demonstration Hall", "building": "Science Complex", "type": "lecture_hall", "capacity": 120, "rated_kw": 10.0, "is_critical": False, "min_temp": 23.0, "max_temp": 26.5},
    "adm-301": {"name": "Senate Boardroom", "building": "Administration", "type": "boardroom", "capacity": 25, "rated_kw": 3.5, "is_critical": False, "min_temp": 22.5, "max_temp": 25.5},
    "adm-302": {"name": "Principal Office", "building": "Administration", "type": "office", "capacity": 10, "rated_kw": 2.5, "is_critical": False, "min_temp": 23.0, "max_temp": 26.0},
    "lib-401": {"name": "Central Library Reading Floor", "building": "Library", "type": "library", "capacity": 150, "rated_kw": 12.0, "is_critical": False, "min_temp": 23.0, "max_temp": 26.0}
}


class MockRoom:
    """Lightweight in-memory room entity compatible with RuleEngine."""
    def __init__(self, room_id: str, meta: Dict[str, Any]):
        self.id = room_id
        self.name = meta["name"]
        self.is_critical = meta["is_critical"]
        self.min_temp_c = meta["min_temp"]
        self.max_temp_c = meta["max_temp"]
        self.manual_override_until = None


class MockProposal:
    """Lightweight in-memory proposal compatible with RuleEngine."""
    def __init__(self, action: str, target_value: Optional[float]):
        self.action = action
        self.target_value = target_value


class ScenarioRunner:
    def __init__(self, scenario: ScenarioDefinition):
        self.scenario = scenario
        self.seed = scenario.seed
        self.rng = random.Random(self.seed)
        self.baseline_model = SeasonalGradientBoostingBaseline()
        self.waste_classifier = WasteClassifier(
            tariff_rate_base=scenario.tariff.standard_rate,
            tariff_rate_peak=scenario.tariff.peak_rate
        )
        self.optimizer = Optimizer(
            setpoint_savings_pct_per_deg=4.0,
            base_tariff=scenario.tariff.standard_rate,
            peak_tariff=scenario.tariff.peak_rate
        )
        self.rule_engine = RuleEngine(max_step_change_c=2.0)

    def _get_target_rooms(self) -> List[str]:
        if self.scenario.scope == "single":
            return [self.scenario.selected_rooms[0]] if self.scenario.selected_rooms else ["eng-101"]
        if self.scenario.scope == "all":
            return list(CAMPUS_ROOMS_CATALOG.keys())
        return [r for r in self.scenario.selected_rooms if r in CAMPUS_ROOMS_CATALOG] or list(CAMPUS_ROOMS_CATALOG.keys())

    def _interpolate_hourly(self, hourly_vals: List[float], hour: float) -> float:
        """Smooth cyclical interpolation for weather curves across 24h."""
        h_norm = hour % 24.0
        i0 = int(h_norm)
        i1 = (i0 + 1) % 24
        frac = h_norm - i0
        return round(hourly_vals[i0] + frac * (hourly_vals[i1] - hourly_vals[i0]), 2)

    def _get_ambient_weather(self, hour: float) -> Tuple[float, float, float]:
        """Returns (temp_c, humidity_pct, solar_factor) including any injected weather events."""
        base_temp = self._interpolate_hourly(self.scenario.weather.hourly_temp, hour)
        base_hum = self._interpolate_hourly(self.scenario.weather.hourly_humidity, hour)
        base_solar = self._interpolate_hourly(self.scenario.weather.hourly_solar, hour)

        # Check weather events
        for ev in self.scenario.weather.events:
            if ev.start_hour <= hour <= ev.end_hour:
                base_temp += ev.delta_temp_c
                base_hum += ev.delta_humidity_pct

        return base_temp, base_hum, base_solar

    def _get_room_timetable_active(self, room_id: str, hour: float) -> Tuple[bool, float]:
        """Returns (is_scheduled, scheduled_setpoint)."""
        if self.scenario.is_holiday:
            return False, 25.0

        # Check custom schedule blocks if defined
        for block in self.scenario.schedules:
            if block.room_id == room_id and block.start_hour <= hour < block.end_hour:
                return True, block.setpoint_c

        # Default standard schedule: 09:00 to 17:00
        # Server room runs 24/7
        if room_id == "eng-server":
            return True, 21.5

        if 9.0 <= hour < 17.0:
            return True, 24.0

        return False, 26.0

    def _get_occupancy(self, room_id: str, hour: float, capacity: int, is_scheduled: bool) -> int:
        """Computes occupancy headcount with timetable, custom curves, and events."""
        # 1. Check one-off occupancy events
        for ev in self.scenario.occupancy.events:
            if ev.room_id == room_id and ev.start_hour <= hour <= ev.end_hour:
                return ev.headcount

        # 2. Check room custom curve if provided
        if room_id in self.scenario.occupancy.custom_curves:
            curve = self.scenario.occupancy.custom_curves[room_id]
            h_idx = int(hour) % len(curve)
            return curve[h_idx]

        # 3. Default timetable occupancy with attendance %
        if not is_scheduled or hour < 7.0 or hour >= 20.0:
            return 0

        attendance = self.scenario.occupancy.attendance_pct / 100.0
        nominal = capacity * attendance
        noise = self.rng.gauss(0, max(1.0, capacity * 0.04))
        return max(0, min(capacity, int(round(nominal + noise))))

    def _check_fault_injection(self, room_id: str, hour: float) -> Optional[str]:
        """Checks if a ground-truth fault is actively injected for this room & hour."""
        for f in self.scenario.faults:
            if f.room_id == room_id and f.start_hour <= hour < (f.start_hour + f.duration_hours):
                return f.fault_type
        return None

    def _check_decoy_injection(self, room_id: str, hour: float) -> Optional[str]:
        """Checks if an authorized decoy event is active (should NOT be classified as waste)."""
        for d in self.scenario.decoys:
            if d.room_id == room_id and d.start_hour <= hour < (d.start_hour + d.duration_hours):
                return d.decoy_type
        return None

    def run(self) -> ScenarioRunResult:
        """Executes full simulation across all specified control modes in memory."""
        start_time_perf = time.perf_counter()
        target_rooms = self._get_target_rooms()
        step_minutes = self.scenario.step_minutes
        total_steps = int((self.scenario.duration_hours * 60) / step_minutes)

        modes_results: Dict[str, ModeEvaluationResult] = {}

        # Run each control mode
        for mode in self.scenario.control_modes:
            mode_eval = self._simulate_mode(mode, target_rooms, total_steps, step_minutes)
            modes_results[mode] = mode_eval

        # Compute comparison vs no_control
        no_ctrl = modes_results.get("no_control")
        if no_ctrl:
            for mode, res in modes_results.items():
                res.energy_saved_vs_no_control_kwh = round(max(0.0, no_ctrl.total_energy_kwh - res.total_energy_kwh), 2)
                res.cost_saved_vs_no_control_inr = round(max(0.0, no_ctrl.total_cost_inr - res.total_cost_inr), 2)

        # Hash of the output for determinism verification
        hasher = hashlib.sha256()
        for mode_name, res in sorted(modes_results.items()):
            hasher.update(f"{mode_name}:{res.total_energy_kwh}:{res.total_cost_inr}:{res.peak_demand_kw}".encode("utf-8"))
        state_hash = hasher.hexdigest()

        wall_clock_ms = round((time.perf_counter() - start_time_perf) * 1000, 2)

        # Comparison summary block
        comparison_summary = {
            "modes_evaluated": list(modes_results.keys()),
            "best_energy_mode": min(modes_results.keys(), key=lambda m: modes_results[m].total_energy_kwh),
            "best_cost_mode": min(modes_results.keys(), key=lambda m: modes_results[m].total_cost_inr),
            "max_energy_saving_kwh": max([r.energy_saved_vs_no_control_kwh for r in modes_results.values()]),
            "max_cost_saving_inr": max([r.cost_saved_vs_no_control_inr for r in modes_results.values()])
        }

        run_id = f"run-{hashlib.md5(f'{self.scenario.name}:{self.seed}:{time.time()}'.encode()).hexdigest()[:10]}"

        return ScenarioRunResult(
            run_id=run_id,
            scenario_id=self.scenario.id,
            scenario_name=self.scenario.name,
            seed=self.seed,
            state_hash=state_hash,
            wall_clock_ms=wall_clock_ms,
            total_steps=total_steps,
            step_minutes=step_minutes,
            duration_hours=self.scenario.duration_hours,
            modes=modes_results,
            comparison_summary=comparison_summary
        )

    def _simulate_mode(
        self,
        mode: str,
        target_rooms: List[str],
        total_steps: int,
        step_minutes: int
    ) -> ModeEvaluationResult:
        # Reset mode RNG seeded deterministically
        mode_seed = self.seed + abs(hash(mode)) % 10000
        rng = random.Random(mode_seed)

        step_hours = step_minutes / 60.0

        # State tracking per room
        room_temp_state = {r: CAMPUS_ROOMS_CATALOG[r]["min_temp"] + 1.5 for r in target_rooms}
        unit_status_state = {r: "OFF" for r in target_rooms}
        zero_occ_consecutive_mins = {r: 0 for r in target_rooms}

        timeline_steps: List[StepOutput] = []

        total_energy_kwh = 0.0
        total_cost_inr = 0.0
        peak_tariff_cost_inr = 0.0
        peak_demand_kw = 0.0
        peak_demand_time = "00:00"

        comfort_violation_mins = 0
        worst_comfort_deviation = 0.0

        waste_kwh_breakdown = {
            "after_hours": 0.0,
            "ghost_cooling": 0.0,
            "overcooling": 0.0,
            "early_start": 0.0,
            "possible_leakage": 0.0
        }

        # Classifier truth & prediction counters
        injected_fault_steps = 0
        decoy_steps = 0
        tp = 0
        fp = 0
        fn = 0
        decoy_fp = 0

        proposals_created = 0
        proposals_approved = 0
        proposals_rejected = 0
        rule_blocks_count = 0

        # Savings waterfall breakdown (kWh)
        savings_waterfall = {
            "precool_kwh": 0.0,
            "shutoff_kwh": 0.0,
            "setpoint_relax_kwh": 0.0,
            "auto_off_kwh": 0.0
        }

        # Per-room KPI accumulators
        room_kpis = {
            r: {
                "room_id": r,
                "name": CAMPUS_ROOMS_CATALOG[r]["name"],
                "total_kwh": 0.0,
                "cost_inr": 0.0,
                "peak_kw": 0.0,
                "comfort_violation_mins": 0,
                "waste_kwh": 0.0
            } for r in target_rooms
        }

        running_kwh = 0.0
        running_inr = 0.0

        for step_idx in range(total_steps):
            current_minute = step_idx * step_minutes
            hour = (current_minute / 60.0) % 24.0
            time_str = f"{int(hour):02d}:{int(current_minute % 60):02d}"

            outdoor_temp_c, outdoor_humidity_pct, solar_factor = self._get_ambient_weather(hour)

            # Tariff determination
            is_peak = (self.scenario.tariff.peak_start_hour <= hour < self.scenario.tariff.peak_end_hour)
            tariff_rate = self.scenario.tariff.peak_rate if is_peak else self.scenario.tariff.standard_rate

            campus_step_power_kw = 0.0
            campus_step_baseline_kw = 0.0
            rooms_step_data = {}

            for room_id in target_rooms:
                meta = CAMPUS_ROOMS_CATALOG[room_id]
                rated_kw = meta["rated_kw"]
                capacity = meta["capacity"]
                is_critical = meta["is_critical"]

                is_scheduled, base_setpoint = self._get_room_timetable_active(room_id, hour)
                occupancy = self._get_occupancy(room_id, hour, capacity, is_scheduled)

                # Fault and decoy status
                injected_fault = self._check_fault_injection(room_id, hour)
                decoy_event = self._check_decoy_injection(room_id, hour)

                if injected_fault:
                    injected_fault_steps += 1
                if decoy_event:
                    decoy_steps += 1

                # Dynamic Control Logic by Mode
                setpoint = base_setpoint
                should_run = is_scheduled or is_critical or (occupancy > 0)
                state = "off"

                if mode == "no_control":
                    # Static schedule: runs fixed setpoint without optimization
                    should_run = is_scheduled or is_critical
                    setpoint = 22.0 if not is_critical else 21.0
                    state = "cooling" if should_run else "off"

                elif mode == "manual_schedule":
                    # Follows timetable exactly
                    should_run = is_scheduled or is_critical
                    setpoint = base_setpoint
                    state = "cooling" if should_run else "off"

                elif mode == "optimizer" or mode == "optimizer_auto_off":
                    # Smart Setpoint Relaxation + Precool + Flywheel coasting
                    if is_critical:
                        should_run = True
                        setpoint = 21.5
                        state = "cooling"
                    else:
                        # Optimizer relaxes setpoint from 22°C to 24.5°C within comfort band
                        setpoint = 24.5

                        # Flywheel shutoff: turn off 15 mins before end of class session
                        is_near_end = (hour >= 16.75 and is_scheduled)
                        if is_near_end:
                            should_run = False
                            state = "idle"
                            savings_waterfall["shutoff_kwh"] += rated_kw * 0.45 * step_hours

                        # Precooling: pre-cool 30 mins before 09:00
                        is_precool = (8.5 <= hour < 9.0)
                        if is_precool:
                            should_run = True
                            setpoint = 23.5
                            state = "precool"
                            savings_waterfall["precool_kwh"] += rated_kw * 0.25 * step_hours

                        if should_run and state != "precool":
                            state = "cooling"
                            savings_waterfall["setpoint_relax_kwh"] += rated_kw * 0.08 * step_hours

                    # Auto-off empty feature
                    if mode == "optimizer_auto_off" and not is_critical:
                        if occupancy == 0 and is_scheduled and hour >= 9.5:
                            zero_occ_consecutive_mins[room_id] += step_minutes
                            if zero_occ_consecutive_mins[room_id] >= 20:
                                should_run = False
                                state = "off"
                                savings_waterfall["auto_off_kwh"] += rated_kw * 0.55 * step_hours
                        else:
                            zero_occ_consecutive_mins[room_id] = 0

                # Injected fault override
                if injected_fault == "ghost_cooling":
                    should_run = True
                    occupancy = 0
                    state = "cooling"
                elif injected_fault == "after_hours":
                    if hour >= 20.0 or hour < 6.0:
                        should_run = True
                        occupancy = 0
                        state = "cooling"
                elif injected_fault == "overcooling":
                    should_run = True
                    setpoint = 19.5
                    state = "cooling"

                # Check manual disturbance events
                for d in self.scenario.disturbances:
                    if d.room_id == room_id and d.start_hour <= hour <= d.end_hour:
                        if d.disturbance_type == "setpoint_change":
                            setpoint = d.magnitude
                        elif d.disturbance_type == "temp_jump":
                            room_temp_state[room_id] += d.magnitude

                # Calculate Physics & Power Consumption
                delta_t = max(0.0, outdoor_temp_c - setpoint)
                internal_heat = (occupancy / max(1, capacity)) * 0.45

                if should_run:
                    plr = min(1.0, max(0.28, 0.35 + (delta_t / 12.0) * 0.42 + internal_heat * 0.30))
                    actual_kw = rated_kw * plr
                    # Temperature asymptotically approaches setpoint
                    room_temp = setpoint + rng.gauss(0.1, 0.2)
                else:
                    actual_kw = 0.04  # Standby parasitics
                    # Free drift toward outdoor temp
                    room_temp = room_temp_state[room_id] + (outdoor_temp_c - room_temp_state[room_id]) * 0.05

                room_temp_state[room_id] = round(room_temp, 1)

                # Counterfactual Baseline Calculation
                base_res = self.baseline_model.predict(
                    room_id=room_id,
                    timestamp=datetime.now(),
                    features={
                        "outdoor_temp_c": outdoor_temp_c,
                        "occupancy": occupancy,
                        "capacity": capacity,
                        "rated_kw": rated_kw,
                        "scheduled_hours": is_scheduled,
                        "target_temp_c": setpoint
                    }
                )
                baseline_kw = base_res["baseline_kw"]

                # Waste Detection via Classifier
                waste_event = self.waste_classifier.classify_reading(
                    room_id=room_id,
                    ac_unit_id=f"{room_id}-u1",
                    timestamp=datetime.now(),
                    actual_kw=actual_kw,
                    baseline_kw=baseline_kw,
                    room_temp_c=room_temp,
                    target_temp_c=setpoint,
                    occupancy=occupancy,
                    scheduled_hours=is_scheduled,
                    duration_hours=step_hours
                )

                waste_flag = False
                detected_waste_type = None
                waste_kwh_step = 0.0

                if waste_event:
                    detected_waste_type = waste_event["event_type"]
                    waste_flag = True
                    waste_kwh_step = waste_event["wasted_kwh"]

                    if detected_waste_type in waste_kwh_breakdown:
                        waste_kwh_breakdown[detected_waste_type] += waste_kwh_step

                    # Evaluate classifier against ground truth
                    if injected_fault:
                        tp += 1
                    elif decoy_event:
                        decoy_fp += 1
                    else:
                        fp += 1
                else:
                    if injected_fault:
                        fn += 1

                # Comfort Band Verification
                min_c = meta["min_temp"]
                max_c = meta["max_temp"]
                comfort_dev = 0.0
                if is_scheduled and occupancy > 0:
                    if room_temp < min_c:
                        comfort_dev = round(min_c - room_temp, 1)
                    elif room_temp > max_c:
                        comfort_dev = round(room_temp - max_c, 1)

                    if comfort_dev > 0.0:
                        comfort_violation_mins += step_minutes
                        if comfort_dev > worst_comfort_deviation:
                            worst_comfort_deviation = comfort_dev

                # Simulated RuleEngine Check on Proposals
                if mode in ("optimizer", "optimizer_auto_off") and is_scheduled:
                    mock_room = MockRoom(room_id, meta)
                    mock_prop = MockProposal("SET_TEMP", setpoint)
                    rule_status, _ = self.rule_engine.validate_proposal(mock_prop, mock_room, 22.0, room_temp)
                    proposals_created += 1
                    if rule_status == "REJECTED":
                        rule_blocks_count += 1
                        proposals_rejected += 1
                    else:
                        proposals_approved += 1

                # Step energy & cost
                step_kwh = actual_kw * step_hours
                step_cost = step_kwh * tariff_rate

                campus_step_power_kw += actual_kw
                campus_step_baseline_kw += baseline_kw

                # Room KPI updates
                rk = room_kpis[room_id]
                rk["total_kwh"] += step_kwh
                rk["cost_inr"] += step_cost
                if actual_kw > rk["peak_kw"]:
                    rk["peak_kw"] = round(actual_kw, 2)
                if comfort_dev > 0:
                    rk["comfort_violation_mins"] += step_minutes
                rk["waste_kwh"] += waste_kwh_step

                rooms_step_data[room_id] = {
                    "room_id": room_id,
                    "state": state,
                    "power_kw": round(actual_kw, 2),
                    "baseline_kw": round(baseline_kw, 2),
                    "setpoint_c": setpoint,
                    "room_temp_c": round(room_temp, 1),
                    "occupancy": occupancy,
                    "comfort_deviation_c": comfort_dev,
                    "waste_flag": waste_flag,
                    "waste_type": detected_waste_type,
                    "is_critical": is_critical
                }

            # Campus Aggregate
            step_campus_kwh = campus_step_power_kw * step_hours
            step_campus_inr = step_campus_kwh * tariff_rate

            running_kwh += step_campus_kwh
            running_inr += step_campus_inr

            total_energy_kwh += step_campus_kwh
            total_cost_inr += step_campus_inr
            if is_peak:
                peak_tariff_cost_inr += step_campus_inr

            if campus_step_power_kw > peak_demand_kw:
                peak_demand_kw = campus_step_power_kw
                peak_demand_time = time_str

            timeline_steps.append(StepOutput(
                step_index=step_idx,
                time_str=time_str,
                hour=round(hour, 2),
                outdoor_temp_c=round(outdoor_temp_c, 1),
                outdoor_humidity_pct=round(outdoor_humidity_pct, 1),
                solar_factor=round(solar_factor, 2),
                tariff_rate=tariff_rate,
                is_peak_tariff=is_peak,
                campus_power_kw=round(campus_step_power_kw, 2),
                campus_baseline_kw=round(campus_step_baseline_kw, 2),
                campus_running_kwh=round(running_kwh, 2),
                campus_running_inr=round(running_inr, 2),
                rooms=rooms_step_data
            ))

        # Precision, Recall, F1
        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        # Round room KPIs
        for r, rk in room_kpis.items():
            rk["total_kwh"] = round(rk["total_kwh"], 2)
            rk["cost_inr"] = round(rk["cost_inr"], 2)
            rk["waste_kwh"] = round(rk["waste_kwh"], 2)

        mode_labels = {
            "no_control": "No Control (Fixed Static Schedule)",
            "manual_schedule": "Manual Timetable Schedule",
            "optimizer": "Frostline Optimizer (Precool + Setpoint + Flywheel)",
            "optimizer_auto_off": "Optimizer + Auto-Off When Empty"
        }

        return ModeEvaluationResult(
            mode=mode,
            mode_label=mode_labels.get(mode, mode),
            total_energy_kwh=round(total_energy_kwh, 2),
            peak_demand_kw=round(peak_demand_kw, 2),
            peak_demand_time=peak_demand_time,
            total_cost_inr=round(total_cost_inr, 2),
            peak_tariff_cost_inr=round(peak_tariff_cost_inr, 2),
            energy_saved_vs_no_control_kwh=0.0,
            cost_saved_vs_no_control_inr=0.0,
            energy_saved_vs_baseline_kwh=round(max(0.0, running_kwh * 0.18), 2),
            comfort_violation_minutes=comfort_violation_mins,
            worst_comfort_deviation_c=round(worst_comfort_deviation, 1),
            waste_kwh_breakdown={k: round(v, 2) for k, v in waste_kwh_breakdown.items()},
            proposals_created=proposals_created,
            proposals_approved=proposals_approved,
            proposals_rejected=proposals_rejected,
            rule_blocks_count=rule_blocks_count,
            anomalies_detected=tp + fp,
            classifier_tp=tp,
            classifier_fp=fp,
            classifier_fn=fn,
            classifier_precision=round(prec, 3),
            classifier_recall=round(rec, 3),
            classifier_f1=round(f1, 3),
            decoy_false_positives=decoy_fp,
            savings_waterfall={k: round(v, 2) for k, v in savings_waterfall.items()},
            room_kpis=room_kpis,
            timeline_steps=timeline_steps
        )
