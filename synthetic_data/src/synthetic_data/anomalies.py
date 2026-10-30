"""
Anomaly and Decoy Scheduler:
Ensures >= 25 events per anomaly type, strictly non-overlapping per AC unit.
Server room is excluded (control group).
Adds >= 10 decoy events per kind with is_legitimate_decoy = True.
"""
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import yaml

from synthetic_data.campus import Campus


class AnomalyManager:
    def __init__(self, rng: np.random.Generator, config_path: str):
        self.rng = rng
        with open(config_path, "r", encoding="utf-8") as f:
            self.raw_config = yaml.safe_load(f)

        self.policy = self.raw_config.get("injection_policy", {})
        self.anomaly_types = self.raw_config.get("anomaly_types", {})
        self.decoy_types = self.raw_config.get("decoy_types", {})

        # Ground truth anomaly records: [{id, room_id, ac_unit_id, anomaly_type, start_time, end_time, severity, is_legitimate_decoy}]
        self.events: list[dict[str, Any]] = []

    def plan_events(self, campus: Campus, start_dt: datetime, end_dt: datetime):
        """
        Pre-schedules non-overlapping anomaly events and legitimate decoys across the time horizon.
        """
        self.events.clear()
        total_hours = int((end_dt - start_dt).total_seconds() / 3600)
        target_per_type = int(self.policy.get("target_events_per_type", 28))
        min_dur_min = int(self.policy.get("min_duration_minutes", 60))
        max_dur_min = int(self.policy.get("max_duration_minutes", 240))
        excluded_rooms = set(self.policy.get("exclude_rooms", ["eng-server"]))

        # Filter candidate rooms & units (excluding server room)
        eligible_rooms = [r for r in campus.all_rooms if r.id not in excluded_rooms]
        eligible_units = [(u.id, r.id) for r in eligible_rooms for u in r.units]

        # Track occupied intervals per unit to guarantee ZERO OVERLAPS
        # unit_id -> list of (start_dt, end_dt)
        unit_schedules: dict[str, list[tuple[datetime, datetime]]] = {uid: [] for uid, _ in eligible_units}

        def has_overlap(uid: str, s: datetime, e: datetime) -> bool:
            for ex_s, ex_e in unit_schedules.get(uid, []):
                # Check interval intersection: max(s, ex_s) < min(e, ex_e)
                if max(s, ex_s) < min(e, ex_e):
                    return True
            return False

        event_counter = 1

        # 1. Plan Core Anomalies (at least 25 per type, targeted 28)
        for anom_type in self.anomaly_types:
            events_placed = 0
            attempts = 0
            max_attempts = target_per_type * 100

            while events_placed < target_per_type and attempts < max_attempts:
                attempts += 1
                # Pick a random unit and room
                unit_id, room_id = eligible_units[self.rng.integers(0, len(eligible_units))]
                dur_minutes = int(self.rng.integers(min_dur_min, max_dur_min + 1, endpoint=True))
                # Align duration to 5 minutes
                dur_minutes = (dur_minutes // 5) * 5

                # Pick start time
                offset_minutes = int(self.rng.integers(0, int(total_hours * 60 - dur_minutes)))
                offset_minutes = (offset_minutes // 5) * 5
                ev_start = start_dt + timedelta(minutes=offset_minutes)
                ev_end = ev_start + timedelta(minutes=dur_minutes)
                computed_precool_start: datetime | None = None
                excess_mins: int | None = None

                # Context-specific timing for realism
                if anom_type == "after_hours":
                    # Must occur during night (22:00 - 05:00) or weekend
                    if not (ev_start.hour >= 22 or ev_start.hour < 5 or ev_start.weekday() in (5, 6)):
                        continue
                elif anom_type == "ghost_cooling":
                    # Daytime weekday class hour
                    if not (9 <= ev_start.hour < 17 and ev_start.weekday() < 5):
                        continue
                elif anom_type == "early_start":
                    # Dynamic early start relative to room's computed morning pre-cool
                    # Find weekday morning schedule for this room
                    room_obj = campus.get_room(room_id)
                    if room_obj is None or ev_start.weekday() >= 5 or campus.is_holiday(ev_start):
                        continue

                    # Search morning schedules for room (start between 08:30 and 11:30)
                    matching_scheds = [
                        s for s in campus.schedules
                        if s.room_id == room_id and s.day_of_week == ev_start.weekday() and 510 <= s.start_minute <= 690
                    ]
                    if not matching_scheds:
                        continue
                    sched_entry = matching_scheds[0]

                    sched_dt = datetime(ev_start.year, ev_start.month, ev_start.day) + timedelta(minutes=sched_entry.start_minute)

                    # Compute room pre-cool pull-down time from typical overnight mass temperature (T_m ~ 28°C)
                    # using project's own calculate_pulldown_time method
                    precool_mins, p_status = room_obj.calculate_pulldown_time(
                        t0=28.0,
                        target_temp=room_obj.target_temp_c,
                        t_out=30.0,
                        q_int_sens_w=0.0
                    )
                    if p_status != "ok":
                        precool_mins = 25.0

                    computed_precool_start = sched_dt - timedelta(minutes=precool_mins)

                    # Configured excess range (default 45 to 120 minutes, ASSUMPTION)
                    min_excess = int(self.policy.get("early_start_excess_min_min", 45))
                    max_excess = int(self.policy.get("early_start_excess_min_max", 120))
                    excess_mins = int(self.rng.integers(min_excess, max_excess + 1))
                    excess_mins = (excess_mins // 5) * 5

                    # Label start = computed pre-cool start minus excess minutes
                    ev_start = computed_precool_start - timedelta(minutes=excess_mins)
                    ev_end = sched_dt

                # Overlap check
                if has_overlap(unit_id, ev_start, ev_end):
                    continue

                # Valid non-overlapping event found
                unit_schedules[unit_id].append((ev_start, ev_end))
                event_dict = {
                    "id": f"gt-anom-{event_counter:04d}",
                    "room_id": room_id,
                    "ac_unit_id": unit_id,
                    "anomaly_type": anom_type,
                    "start_time": ev_start,
                    "end_time": ev_end,
                    "severity": 1.0,
                    "is_legitimate_decoy": False
                }
                if anom_type == "early_start":
                    event_dict["computed_precool_start"] = computed_precool_start
                    event_dict["excess_minutes"] = excess_mins
                self.events.append(event_dict)
                event_counter += 1
                events_placed += 1

        # 2. Plan Decoy Events (at least 10 per kind)
        for decoy_type, cfg in self.decoy_types.items():
            target_decoy = int(cfg.get("target_count", 12))
            decoys_placed = 0
            attempts = 0
            max_attempts = target_decoy * 100

            while decoys_placed < target_decoy and attempts < max_attempts:
                attempts += 1
                unit_id, room_id = eligible_units[self.rng.integers(0, len(eligible_units))]
                dur_minutes = int(self.rng.integers(60, 180))
                dur_minutes = (dur_minutes // 5) * 5
                offset_minutes = int(self.rng.integers(0, int(total_hours * 60 - dur_minutes)))
                offset_minutes = (offset_minutes // 5) * 5
                ev_start = start_dt + timedelta(minutes=offset_minutes)
                ev_end = ev_start + timedelta(minutes=dur_minutes)

                if decoy_type == "late_lab_exception":
                    # Late evening (19:00 - 23:00)
                    if not (19 <= ev_start.hour <= 22):
                        continue
                elif decoy_type == "exam_overrun":
                    # Afternoon (12:00 - 15:00 or 17:00 - 19:00)
                    if not (12 <= ev_start.hour <= 18 and ev_start.weekday() < 5):
                        continue

                if has_overlap(unit_id, ev_start, ev_end):
                    continue

                unit_schedules[unit_id].append((ev_start, ev_end))
                self.events.append({
                    "id": f"gt-decoy-{event_counter:04d}",
                    "room_id": room_id,
                    "ac_unit_id": unit_id,
                    "anomaly_type": decoy_type,
                    "start_time": ev_start,
                    "end_time": ev_end,
                    "severity": 1.0,
                    "is_legitimate_decoy": True
                })
                event_counter += 1
                decoys_placed += 1

    def get_active_event(self, room_id: str, unit_id: str, dt: datetime) -> dict[str, Any] | None:
        for ev in self.events:
            if ev["ac_unit_id"] == unit_id:
                if ev["start_time"] <= dt < ev["end_time"]:
                    return ev
        return None

    def get_ground_truth_dataframe(self):
        import pandas as pd
        if not self.events:
            return pd.DataFrame(columns=[
                "id", "room_id", "ac_unit_id", "anomaly_type",
                "start_time", "end_time", "severity", "is_legitimate_decoy"
            ])
        return pd.DataFrame(self.events)
