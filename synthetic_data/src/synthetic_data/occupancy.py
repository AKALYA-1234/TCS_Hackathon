"""
Occupancy simulation: Simulates actual headcount, smooth arrival/departure ramps,
and noisy CV camera bounding-box readings.
"""
from datetime import datetime
from typing import Any

import numpy as np

from synthetic_data.campus import Campus, Room


class OccupancySimulator:
    def __init__(self, rng: np.random.Generator, config: dict[str, Any]):
        self.rng = rng
        self.att_min = config.get("attendance_ratio_min", 0.72)
        self.att_max = config.get("attendance_ratio_max", 0.94)
        self.noise_std = config.get("headcount_noise_std", 1.1)
        self.conf_min = config.get("confidence_min", 0.88)
        self.conf_max = config.get("confidence_max", 0.98)
        self.arr_ramp_mins = 20.0
        self.dep_ramp_mins = 15.0

    def simulate_occupancy(
        self,
        room: Room,
        campus: Campus,
        dt: datetime,
        force_zero: bool = False,
        decoy_headcount: int | None = None
    ) -> dict[str, Any]:
        """
        Simulates ground-truth headcount with smooth transitions and camera CV detection.
        """
        if force_zero:
            return {
                "ground_truth_headcount": 0,
                "cv_headcount": 0,
                "cv_confidence": round(float(self.rng.uniform(self.conf_min, self.conf_max)), 2),
                "is_scheduled": False,
                "activity_name": None,
                "expected_headcount": 0
            }

        if decoy_headcount is not None:
            # Authorized exception decoy (e.g. late lab or exam overrun)
            gt_headcount = min(room.capacity, decoy_headcount)
            cv_noise = self.rng.normal(0, self.noise_std)
            cv_detected = int(np.clip(np.round(gt_headcount + cv_noise), 0, room.capacity))
            return {
                "ground_truth_headcount": gt_headcount,
                "cv_headcount": cv_detected,
                "cv_confidence": round(float(self.rng.uniform(self.conf_min, self.conf_max)), 2),
                "is_scheduled": False,
                "activity_name": "Authorized Decoy Activity",
                "expected_headcount": 0
            }

        hour = dt.hour
        time_minutes = dt.hour * 60 + dt.minute
        dow = dt.weekday()
        sched = campus.get_active_schedule(room.id, dt)

        # Holiday check
        if campus.is_holiday(dt) and not room.is_critical:
            return {
                "ground_truth_headcount": 0,
                "cv_headcount": 0,
                "cv_confidence": round(float(self.rng.uniform(self.conf_min, self.conf_max)), 2),
                "is_scheduled": False,
                "activity_name": "Campus Holiday",
                "expected_headcount": 0
            }

        # Server rooms are permanently 0 (or 1 engineer during maintenance)
        if room.room_type == "server_room":
            srv_occ = 1 if (self.rng.random() < 0.02 and 10 <= hour < 16 and dow < 5) else 0
            return {
                "ground_truth_headcount": srv_occ,
                "cv_headcount": srv_occ,
                "cv_confidence": 0.98,
                "is_scheduled": False,
                "activity_name": "Server Monitoring",
                "expected_headcount": 0
            }

        # Unoccupied late night (22:00 to 06:00) or weekends (unless critical lab)
        if (hour >= 22 or hour < 6) or (dow in (5, 6) and not room.is_critical):
            return {
                "ground_truth_headcount": 0,
                "cv_headcount": 0,
                "cv_confidence": round(float(self.rng.uniform(self.conf_min, self.conf_max)), 2),
                "is_scheduled": False,
                "activity_name": None,
                "expected_headcount": 0
            }

        if sched is not None:
            # Scheduled lecture / session
            expected_hc = sched["expected_headcount"]
            start_m = sched["start_minute"]
            end_m = sched["end_minute"]

            # Arrival ramp factor: smooth progression from 0 to 1 over first 20 mins
            if time_minutes < start_m + self.arr_ramp_mins:
                ramp = (time_minutes - start_m) / max(1.0, self.arr_ramp_mins)
                ramp = max(0.15, min(1.0, ramp))
            # Departure ramp factor: smooth drop over last 15 mins
            elif time_minutes > end_m - self.dep_ramp_mins:
                ramp = (end_m - time_minutes) / max(1.0, self.dep_ramp_mins)
                ramp = max(0.10, min(1.0, ramp))
            else:
                ramp = 1.0

            ratio = self.rng.uniform(self.att_min, self.att_max)
            nominal = expected_hc * ratio * ramp
            gt_headcount = int(np.clip(np.round(nominal), 0, room.capacity))
            is_sched = True
            activity = sched["activity_name"]
        else:
            # Off-schedule daytime (study/office work)
            is_sched = False
            expected_hc = 0
            activity = "Unscheduled Study / Office Work"
            if room.room_type == "office":
                gt_headcount = int(self.rng.integers(1, max(2, room.capacity // 2))) if (9 <= hour < 18) else 0
            elif room.room_type in ("lab", "computer_lab"):
                gt_headcount = int(self.rng.integers(0, 5)) if (9 <= hour < 19) else 0
            else:
                gt_headcount = int(self.rng.integers(0, 3)) if (self.rng.random() < 0.12 and 8 <= hour < 20) else 0

        # Simulate Computer Vision camera reading with bounding-box noise
        cv_noise = self.rng.normal(0, self.noise_std)
        cv_detected = int(np.clip(np.round(gt_headcount + cv_noise), 0, room.capacity))
        confidence = float(self.rng.uniform(self.conf_min, self.conf_max))

        return {
            "ground_truth_headcount": gt_headcount,
            "cv_headcount": cv_detected,
            "cv_confidence": round(confidence, 2),
            "is_scheduled": is_sched,
            "activity_name": activity,
            "expected_headcount": expected_hc
        }
