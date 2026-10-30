"""
Dataset Provider Interface and Implementations:
- DatasetProvider (ABC)
- SyntheticProvider (Diurnal sinusoidal load, weather dependence, timetable-driven headcount)
- AshraeProvider (Stub for ASHRAE GEPIII chilled-water meter=1 dataset)
"""
from abc import ABC, abstractmethod
import math
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional


class DatasetProvider(ABC):
    @abstractmethod
    def get_outdoor_temperature(self, timestamp: datetime) -> float:
        """Returns outdoor ambient temperature in Celsius."""
        pass

    @abstractmethod
    def get_room_occupancy(self, room_id: str, timestamp: datetime, capacity: int, schedule_active: bool) -> int:
        """Returns simulated/measured headcount in the room."""
        pass

    @abstractmethod
    def get_cooling_demand_kw(
        self,
        room_id: str,
        timestamp: datetime,
        rated_kw: float,
        occupancy: int,
        capacity: int,
        outdoor_temp_c: float,
        set_temp_c: float,
        is_on: bool,
        injected_anomaly: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculates power consumption, indoor temperature, and anomaly indicators."""
        pass


class SyntheticProvider(DatasetProvider):
    """
    Simulates thermal dynamics with daily sinusoidal outdoor temperatures,
    occupancy based on schedule * attendance with Gaussian CV noise,
    and physics-based AC compressor power draw.
    """
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def get_outdoor_temperature(self, timestamp: datetime) -> float:
        # Peak outdoor temperature at 15:00 (~35°C), minimum at 05:00 (~23°C) in summer campus
        hour = timestamp.hour + timestamp.minute / 60.0
        # Sinusoid shifted so peak is around hour 15
        rad = (hour - 9) * (2 * math.pi / 24)
        diurnal = math.sin(rad)
        base_temp = 29.0 + (6.0 * diurnal)
        noise = self.rng.gauss(0, 0.4)
        return round(base_temp + noise, 1)

    def get_room_occupancy(self, room_id: str, timestamp: datetime, capacity: int, schedule_active: bool) -> int:
        hour = timestamp.hour
        # If outside operational hours (21:00 - 06:00), room is empty
        if hour >= 21 or hour < 6:
            return 0

        if schedule_active:
            # Typical attendance ~70-90% of enrollment
            attendance_factor = self.rng.uniform(0.70, 0.90)
            nominal = capacity * attendance_factor
            # Simulated CV camera headcount noise (+/- 2 students)
            noise = self.rng.gauss(0, 1.5)
            count = max(0, min(capacity, int(round(nominal + noise))))
            return count
        else:
            # Off-schedule (e.g. break or evening): 0-3 stray occupants occasionally
            if self.rng.random() < 0.2:
                return self.rng.randint(1, min(3, capacity))
            return 0

    def get_cooling_demand_kw(
        self,
        room_id: str,
        timestamp: datetime,
        rated_kw: float,
        occupancy: int,
        capacity: int,
        outdoor_temp_c: float,
        set_temp_c: float,
        is_on: bool,
        injected_anomaly: Optional[str] = None
    ) -> Dict[str, Any]:
        if not is_on:
            # Standby parasitics ~ 30W
            indoor_temp = max(24.0, outdoor_temp_c - 3.0)
            return {
                "power_kw": 0.03,
                "room_temp_c": round(indoor_temp, 1),
                "cop": 0.0,
                "anomaly": None
            }

        # Thermal load components:
        # 1. Envelope heat gain ~ delta T (outdoor - indoor)
        delta_t = max(0.0, outdoor_temp_c - set_temp_c)
        envelope_factor = (delta_t / 12.0)  # normalized
        
        # 2. Internal heat gain ~ 100W per person + lighting/laptops
        internal_factor = (occupancy / max(1, capacity)) * 0.45
        
        # 3. Base chiller/inverter modulation ratio
        part_load_ratio = min(1.0, max(0.25, 0.35 + 0.45 * envelope_factor + 0.30 * internal_factor))

        # Base nominal power in kW
        power = rated_kw * part_load_ratio

        # Room indoor temperature naturally approaches setpoint with slight drift
        room_temp = set_temp_c + self.rng.gauss(0.2, 0.3)

        # Apply Injected Anomalies (Ground Truth)
        active_anomaly = injected_anomaly
        if injected_anomaly == "ghost_cooling":
            # Running at high power while occupancy is 0
            power = rated_kw * 0.85
            room_temp = set_temp_c - 0.5
        elif injected_anomaly == "overcooling":
            # Sub-comfort freeze (e.g. 19-20°C instead of 24°C)
            power = rated_kw * 0.95
            room_temp = min(20.0, set_temp_c - 3.0)
        elif injected_anomaly == "after_hours":
            # Running late night / weekend empty
            power = rated_kw * 0.70
            room_temp = set_temp_c
        elif injected_anomaly == "early_start":
            # Pre-cooling turned on 3 hours too early
            power = rated_kw * 0.80
            room_temp = set_temp_c
        elif injected_anomaly == "possible_leakage":
            # Compressor running at 100% rated kW, but indoor temp is NOT dropping (refrigerant leak or door open)
            power = rated_kw * 1.05
            room_temp = max(27.0, outdoor_temp_c - 1.5)

        return {
            "power_kw": round(power, 2),
            "room_temp_c": round(room_temp, 1),
            "cop": 3.2,
            "anomaly": active_anomaly
        }


class AshraeProvider(DatasetProvider):
    """
    Stub for ASHRAE Great Energy Predictor III (GEPIII) chilled water meter dataset.
    Reads `meter=1` (chilled water) from education buildings and `weather_train.csv`
    once real datasets are dropped in by the user.
    """
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or "data/ashrae"
        self._loaded = False

    def get_outdoor_temperature(self, timestamp: datetime) -> float:
        # Fallback to synthetic if CSVs are not yet supplied
        return 31.5

    def get_room_occupancy(self, room_id: str, timestamp: datetime, capacity: int, schedule_active: bool) -> int:
        return int(capacity * 0.7) if schedule_active else 0

    def get_cooling_demand_kw(
        self,
        room_id: str,
        timestamp: datetime,
        rated_kw: float,
        occupancy: int,
        capacity: int,
        outdoor_temp_c: float,
        set_temp_c: float,
        is_on: bool,
        injected_anomaly: Optional[str] = None
    ) -> Dict[str, Any]:
        # Placeholder calculation mimicking building chilled water load scaled to room
        if not is_on:
            return {"power_kw": 0.05, "room_temp_c": 26.0, "anomaly": None}
        return {
            "power_kw": round(rated_kw * 0.65, 2),
            "room_temp_c": set_temp_c,
            "anomaly": injected_anomaly
        }
