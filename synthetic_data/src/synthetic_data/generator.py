"""
Synthetic Data Orchestrator:
Runs full simulation loop at configurable resolution (1 to 60 mins, default 5 mins),
produces main telemetry file, extended telemetry file, counterfactuals, weather,
occupancy, tariffs, schedules, and ground truth labels.
Strictly ensures zero leakage of anomaly labels into main file.
"""
import logging
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yaml

from synthetic_data.anomalies import AnomalyManager
from synthetic_data.campus import Campus
from synthetic_data.occupancy import OccupancySimulator
from synthetic_data.physics import ThermalPhysicsEngine
from synthetic_data.profiles import AshraeProfileAnchor

logger = logging.getLogger("synthetic_data.generator")


class SyntheticDataGenerator:
    def __init__(
        self,
        default_config_path: str,
        rooms_config_path: str,
        anomalies_config_path: str
    ):
        with open(default_config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.seed = int(self.config.get("seed", 42))
        self.rng = np.random.default_rng(self.seed)

        logger.info(f"Initializing SyntheticDataGenerator with seed={self.seed}")
        self.campus = Campus.from_yaml(rooms_config_path, default_config_path)

        parquet_path = self.config["ashrae"]["parquet_path"]
        if not os.path.exists(parquet_path):
            alt_path = os.path.join(os.path.dirname(__file__), "../../../", "dataset_processed/ashrae_chilled_selected.parquet")
            if os.path.exists(alt_path):
                parquet_path = os.path.abspath(alt_path)

        fallback = bool(self.config["ashrae"].get("fallback_if_missing", True))
        tz_offset = int(self.config["ashrae"].get("timezone_offset_hours", -8))
        self.profile_anchor = AshraeProfileAnchor(
            parquet_path,
            fallback_if_missing=fallback,
            timezone_offset_hours=tz_offset
        )
        self.occupancy_sim = OccupancySimulator(self.rng, self.config.get("cv_occupancy", {}))
        self.physics_engine = ThermalPhysicsEngine(self.rng, self.config)
        self.anomaly_mgr = AnomalyManager(self.rng, anomalies_config_path)

    def generate(self) -> dict[str, pd.DataFrame]:
        time_cfg = self.config.get("time_horizon", {})
        start_dt = datetime.fromisoformat(time_cfg.get("start_date", "2026-06-01 00:00:00"))
        end_dt = datetime.fromisoformat(time_cfg.get("end_date", "2026-07-30 23:55:00"))
        step_mins = int(time_cfg.get("step_minutes", 5))

        logger.info(f"Generating synthetic telemetry from {start_dt} to {end_dt} ({step_mins}-min resolution, 60 days)")

        # 1. Plan anomalies and decoys
        self.anomaly_mgr.plan_events(self.campus, start_dt, end_dt)

        main_telemetry_rows = []
        extended_telemetry_rows = []
        counterfactual_rows = []
        occupancy_rows = []
        weather_rows = []
        weather_visited = set()

        curr_dt = start_dt
        step_delta = timedelta(minutes=step_mins)
        room_precool_active_until: dict[str, datetime] = {}

        tariff_cfg = self.config.get("tariff", {})
        base_rate = float(tariff_cfg.get("base_rate_per_kwh", 8.50))
        peak_rate = float(tariff_cfg.get("peak_rate_per_kwh", 12.50))
        peak_start = int(tariff_cfg.get("peak_start_hour", 14))
        peak_end = int(tariff_cfg.get("peak_end_hour", 18))

        # Max pre-cool minutes from config
        max_precool = float(self.config.get("physics", {}).get("max_precool_minutes", 180.0))
        shr = float(self.config.get("physics", {}).get("shr_default", 0.75))

        while curr_dt <= end_dt:
            # Weather point for current interval
            weather_pt = self.profile_anchor.get_profile_point(173, curr_dt)
            outdoor_temp = weather_pt["outdoor_temp_c"]
            humidity = weather_pt["relative_humidity"]

            is_peak = (peak_start <= curr_dt.hour < peak_end and curr_dt.weekday() < 5 and not self.campus.is_holiday(curr_dt))
            tariff_rate = peak_rate if is_peak else base_rate

            if curr_dt not in weather_visited:
                weather_visited.add(curr_dt)
                weather_rows.append({
                    "id": f"wth-{curr_dt.strftime('%Y%m%d%H%M')}",
                    "timestamp": curr_dt,
                    "outdoor_temp_c": outdoor_temp,
                    "relative_humidity": humidity,
                    "solar_irradiance_wm2": round(max(0.0, np.sin(max(0, curr_dt.hour - 6) * np.pi / 12) * 850.0 + float(self.rng.normal(0, 15.0))), 1) if (6 <= curr_dt.hour <= 18) else 0.0
                })

            for building in self.campus.buildings:
                for room in building.rooms:
                    # Check active events on room/units
                    active_events = [self.anomaly_mgr.get_active_event(room.id, u.id, curr_dt) for u in room.units]
                    has_ghost = any(e is not None and e.get("anomaly_type") == "ghost_cooling" for e in active_events)
                    has_after = any(e is not None and e.get("anomaly_type") == "after_hours" for e in active_events)

                    decoy_hc = None
                    for e in active_events:
                        if e is not None and e.get("is_legitimate_decoy"):
                            decoy_hc = 5 if e["anomaly_type"] == "late_lab_exception" else (35 if e["anomaly_type"] == "exam_overrun" else 25)

                    force_zero_occ = (has_ghost or has_after)

                    occ_res = self.occupancy_sim.simulate_occupancy(
                        room, self.campus, curr_dt,
                        force_zero=force_zero_occ,
                        decoy_headcount=decoy_hc
                    )

                    occupancy_rows.append({
                        "id": f"occ-{room.id}-{curr_dt.strftime('%Y%m%d%H%M')}",
                        "room_id": room.id,
                        "timestamp": curr_dt,
                        "headcount": occ_res["cv_headcount"],
                        "confidence": occ_res["cv_confidence"],
                        "is_synthetic": True
                    })

                    is_sched = occ_res["is_scheduled"]
                    exp_headcount = occ_res["expected_headcount"]

                    # Pre-cool time calculation based on room's CURRENT mass temperature
                    _t_a, t_m = self.physics_engine.get_room_temperatures(room)
                    q_sens_int, _ = self.physics_engine.calculate_internal_heat_gains(room, 0, False)
                    precool_mins, pulldown_status = room.calculate_pulldown_time(
                        t0=t_m,  # Warm mass start requires longer pull-down
                        target_temp=room.target_temp_c,
                        t_out=outdoor_temp,
                        q_int_sens_w=q_sens_int,
                        shr=shr,
                        max_precool_mins=max_precool
                    )

                    # Check if next class starts within precool_mins or already in precool cycle
                    is_in_precool = False
                    if not is_sched and curr_dt.weekday() < 5 and pulldown_status == "ok":
                        # Check if within an active precool window
                        active_until = room_precool_active_until.get(room.id)
                        if active_until is not None and curr_dt < active_until:
                            is_in_precool = True
                        else:
                            # Look ahead for upcoming scheduled class
                            for offset_m in range(5, int(max_precool) + 5, 5):
                                future_dt = curr_dt + timedelta(minutes=offset_m)
                                future_sched = self.campus.get_active_schedule(room.id, future_dt)
                                if future_sched is not None and future_sched.get("is_scheduled"):
                                    if offset_m <= precool_mins + 5:
                                        is_in_precool = True
                                        room_precool_active_until[room.id] = future_dt
                                    break
                    elif is_sched:
                        room_precool_active_until.pop(room.id, None)

                    is_workday = (curr_dt.weekday() < 5 and 8 <= curr_dt.hour < 19 and not self.campus.is_holiday(curr_dt))
                    normal_on = room.is_critical or is_sched or is_in_precool or (is_workday and occ_res["ground_truth_headcount"] > 0)

                    n_room_units = max(1, len(room.units))
                    unit_step_mins = step_mins / n_room_units
                    self.physics_engine.get_room_temperatures(room)[0]

                    # Step each unit and collect telemetry
                    step_unit_telems = []
                    for unit in room.units:
                        unit_event = self.anomaly_mgr.get_active_event(room.id, unit.id, curr_dt)
                        anom_type = unit_event["anomaly_type"] if unit_event and not unit_event["is_legitimate_decoy"] else None

                        is_on = normal_on
                        if anom_type in ("after_hours", "ghost_cooling", "overcooling", "early_start", "possible_leakage") or unit_event and unit_event["is_legitimate_decoy"]:
                            is_on = True

                        telem = self.physics_engine.step_room_telemetry(
                            room=room,
                            unit=unit,
                            outdoor_temp_c=outdoor_temp,
                            occupancy_headcount=occ_res["ground_truth_headcount"],
                            is_on_commanded=is_on,
                            set_temp_c=room.target_temp_c,
                            dt_minutes=unit_step_mins,
                            injected_anomaly=anom_type
                        )

                        # Counterfactual normal power
                        cf_kw = self.physics_engine.calculate_counterfactual_power(
                            room=room,
                            unit=unit,
                            outdoor_temp_c=outdoor_temp,
                            occupancy_headcount=occ_res["ground_truth_headcount"],
                            is_scheduled=is_sched
                        )

                        step_unit_telems.append((unit, telem, cf_kw, anom_type))

                    # Room state temperature after all units have stepped for this 5-min interval
                    step_end_t_a = self.physics_engine.room_states[room.id][0]
                    date_time_str = curr_dt.strftime("%Y-%m-%d %H:%M:%S")

                    for unit, telem, cf_kw, anom_type in step_unit_telems:
                        # Synchronized room temperature across units (with individual sensor noise)
                        # Overcooling anomaly overrides to 19.6 C; possible_leakage sets elevated temp
                        if anom_type == "overcooling":
                            unit_room_temp = 19.6
                        elif anom_type == "possible_leakage":
                            unit_room_temp = telem["room_temp_c"]
                        else:
                            noise_t = float(self.physics_engine.rng.normal(0, self.physics_engine.temp_noise_std))
                            unit_room_temp = float(np.clip(round(step_end_t_a + noise_t, 1), 16.0, 42.0))

                        # Main telemetry (STRICT CONTRACT: exactly 9 columns, NO LABELS)
                        main_telemetry_rows.append({
                            "room": room.id,
                            "ac_unit_id": unit.id,
                            "date_time": date_time_str,
                            "power_kw": telem["power_kw"],
                            "set_temp_c": telem["set_temp_c"],
                            "room_temp_c": unit_room_temp,
                            "occupancy": occ_res["cv_headcount"],
                            "on_off_status": telem["on_off_status"],
                            "scheduled_hours": is_sched
                        })

                        # Extended telemetry
                        extended_telemetry_rows.append({
                            "room": room.id,
                            "ac_unit_id": unit.id,
                            "date_time": date_time_str,
                            "outdoor_temp_c": outdoor_temp,
                            "humidity": humidity,
                            "expected_headcount": exp_headcount,
                            "is_peak": is_peak,
                            "tariff_inr_per_kwh": tariff_rate
                        })

                        # Counterfactual
                        wasted_kw = max(0.0, telem["power_kw"] - cf_kw)
                        counterfactual_rows.append({
                            "room": room.id,
                            "ac_unit_id": unit.id,
                            "date_time": date_time_str,
                            "actual_power_kw": telem["power_kw"],
                            "counterfactual_power_kw": cf_kw,
                            "wasted_power_kw": round(wasted_kw, 3),
                            "wasted_energy_kwh": round(wasted_kw * (step_mins / 60.0), 4),
                            "wasted_cost_inr": round(wasted_kw * (step_mins / 60.0) * tariff_rate, 4)
                        })

            curr_dt += step_delta

        df_main = pd.DataFrame(main_telemetry_rows)
        df_ext = pd.DataFrame(extended_telemetry_rows)
        df_cf = pd.DataFrame(counterfactual_rows)
        df_occ = pd.DataFrame(occupancy_rows)
        df_wth = pd.DataFrame(weather_rows)
        df_gt = self.anomaly_mgr.get_ground_truth_dataframe()

        # Metadata tables with new sizing_status and 2R2C parameters
        df_rooms = pd.DataFrame([
            {
                "id": r.id,
                "building": r.building,
                "name": r.name,
                "room_type": r.room_type,
                "area_sqm": r.area_sqm,
                "height_m": r.height_m,
                "capacity": r.capacity,
                "target_temp_c": r.target_temp_c,
                "min_temp_c": r.min_temp_c,
                "max_temp_c": r.max_temp_c,
                "is_critical": r.is_critical,
                "design_load_w": r.design_load_w,
                "rated_sensible_cooling_w": r.rated_sensible_cooling_w,
                "sizing_status": r.sizing_status,
                "sizing_margin_pct": r.sizing_margin_pct,
                "tau_passive_hours": round(r.tau_passive_hours, 2)
            }
            for r in self.campus.all_rooms
        ])

        df_units = pd.DataFrame([
            {
                "id": u.id,
                "room_id": r.id,
                "name": u.name,
                "rated_kw": u.rated_kw,
                "control_type": u.control_type,
                "cop": u.cop
            }
            for u, r in [(u, r) for b in self.campus.buildings for r in b.rooms for u in r.units]
        ])

        # Tariff definition table
        df_tariffs = pd.DataFrame([
            {
                "id": "tariff-campus-tou",
                "label": "ASSUMPTION: Campus Time-of-Use Tariff",
                "currency": tariff_cfg.get("currency", "INR"),
                "base_rate_per_kwh": base_rate,
                "peak_rate_per_kwh": peak_rate,
                "peak_start_hour": peak_start,
                "peak_end_hour": peak_end
            }
        ])

        # Timetable definition table
        df_schedules = pd.DataFrame([
            {
                "room_id": s.room_id,
                "day_of_week": s.day_of_week,
                "start_time": s.start_time_str,
                "end_time": s.end_time_str,
                "activity_name": s.activity_name,
                "expected_headcount": s.expected_headcount
            }
            for s in self.campus.schedules
        ])

        return {
            "ac_telemetry": df_main,
            "ac_telemetry_extended": df_ext,
            "ac_counterfactual": df_cf,
            "occupancy_readings": df_occ,
            "weather": df_wth,
            "ground_truth_labels": df_gt,
            "rooms": df_rooms,
            "ac_units": df_units,
            "tariffs": df_tariffs,
            "schedules": df_schedules
        }
