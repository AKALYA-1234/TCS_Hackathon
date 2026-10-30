"""
Campus hierarchy models: Building, Room, ACUnit, TimetableEntry, SpecialEvent.
Integrates 2R2C room thermal parameters, design load sizing, and capacity pull-down formula.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import yaml


@dataclass(frozen=True)
class ACUnit:
    id: str
    name: str
    rated_kw: float
    control_type: str = "inverter"  # "inverter" or "fixed_speed"
    cop: float = 3.2


@dataclass
class Room:
    id: str
    building: str
    name: str
    room_type: str
    area_sqm: float
    height_m: float
    capacity: int
    target_temp_c: float
    min_temp_c: float
    max_temp_c: float
    is_critical: bool
    thermal_multiplier: float
    c_a: float                      # Air node capacitance (J/K)
    c_m: float                      # Mass node capacitance (J/K)
    r_ao: float                     # Air-to-outdoor thermal resistance (K/W)
    r_am: float                     # Air-to-mass thermal resistance (K/W)
    design_load_w: float = 0.0      # Calculated summer design load (W)
    rated_sensible_cooling_w: float = 0.0 # Total rated sensible cooling capacity (W)
    sizing_status: str = "ok"       # "ok", "marginal", "undersized"
    sizing_margin_pct: float = 0.0  # (Rated - Design) / Design * 100
    units: list[ACUnit] = field(default_factory=list)

    @property
    def total_rated_kw(self) -> float:
        return sum(u.rated_kw for u in self.units)

    @property
    def volume_m3(self) -> float:
        return self.area_sqm * self.height_m

    @property
    def tau_passive_hours(self) -> float:
        """Passive lump thermal time constant in hours: R_ao * (C_a + C_m) / 3600."""
        return (self.r_ao * (self.c_a + self.c_m)) / 3600.0

    def calculate_pulldown_time(
        self,
        t0: float,
        target_temp: float,
        t_out: float,
        q_int_sens_w: float,
        shr: float = 0.75,
        max_precool_mins: float = 180.0
    ) -> tuple[float, str]:
        """
        Pull-down formula based on sensible cooling capacity:
          T_eq = T_out + R_ao * (Q_int_sens - Q_cool_sens)
          t_pulldown = tau * ln((T0 - T_eq) / (T_target - T_eq))
        
        Returns (pulldown_minutes, status) where status is 'ok' or 'cannot_reach'.
        """
        if t0 <= target_temp:
            return 0.0, "ok"

        q_cool_sens_w = self.total_rated_kw * 1000.0 * shr
        t_eq = t_out + self.r_ao * (q_int_sens_w - q_cool_sens_w)

        # If T_eq >= target_temp, cooling capacity is insufficient to reach setpoint
        if t_eq >= target_temp:
            return max_precool_mins, "cannot_reach"

        num = t0 - t_eq
        den = target_temp - t_eq

        if den <= 0 or num <= 0:
            return max_precool_mins, "cannot_reach"

        # Effective time constant for air and interior surface mass pull-down
        # Effective mass participation during pre-cool pull-down (~55%, ASSUMPTION)
        c_eff = self.c_a + 0.55 * self.c_m
        tau_eff_hours = (self.r_ao * c_eff) / 3600.0

        try:
            ratio = num / den
            if ratio <= 1.0:
                return 0.0, "ok"
            hours = tau_eff_hours * math.log(ratio)
            mins = hours * 60.0
            return float(min(max_precool_mins, max(10.0, mins))), "ok"
        except (ValueError, ZeroDivisionError):
            return max_precool_mins, "cannot_reach"


@dataclass(frozen=True)
class Building:
    id: str
    name: str
    archetype_building_id: int
    rooms: list[Room] = field(default_factory=list)


@dataclass(frozen=True)
class TimetableEntry:
    room_id: str
    day_of_week: int
    start_time_str: str
    end_time_str: str
    activity_name: str
    expected_headcount: int

    @property
    def start_minute(self) -> int:
        parts = self.start_time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    @property
    def end_minute(self) -> int:
        parts = self.end_time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])


@dataclass(frozen=True)
class SpecialEvent:
    id: str
    room_id: str
    event_date: str
    start_time_str: str
    end_time_str: str
    activity_name: str
    expected_headcount: int


class Campus:
    def __init__(
        self,
        buildings: list[Building],
        schedules: list[TimetableEntry],
        special_events: list[SpecialEvent],
        holidays: list[str]
    ):
        self.buildings = buildings
        self.schedules = schedules
        self.special_events = special_events
        self.holidays = set(holidays)
        self._rooms_by_id = {r.id: r for b in buildings for r in b.rooms}
        self._units_by_id = {u.id: (u, r) for b in buildings for r in b.rooms for u in r.units}
        self._building_by_room_id = {r.id: b for b in buildings for r in b.rooms}

    @classmethod
    def from_yaml(cls, rooms_path: str, config_path: str) -> "Campus":
        with open(rooms_path, "r", encoding="utf-8") as f:
            rooms_data = yaml.safe_load(f)
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        phys_cfg = cfg.get("physics", {})
        rho_air = float(phys_cfg.get("rho_air", 1.18))
        cp_air = float(phys_cfg.get("cp_air", 1006.0))
        shr = float(phys_cfg.get("shr_default", 0.75))
        gains_cfg = cfg.get("internal_gains", {})

        # Peak summer design temperature (Site 2 peak outdoor temp is ~45.0°C)

        buildings = []
        for b_raw in rooms_data.get("buildings", []):
            rooms = []
            for r_raw in b_raw.get("rooms", []):
                units = [
                    ACUnit(
                        id=u["id"],
                        name=u["name"],
                        rated_kw=float(u["rated_kw"]),
                        control_type=u.get("control_type", "inverter"),
                        cop=float(u.get("cop", 3.2))
                    )
                    for u in r_raw.get("units", [])
                ]

                area = float(r_raw["area_sqm"])
                height = float(r_raw.get("height_m", 3.0))
                volume = area * height
                room_type = r_raw["room_type"]
                type_gains = gains_cfg.get(room_type, gains_cfg.get("office", {}))

                # 2R2C thermal parameters
                # Air capacitance C_a (J/K)
                c_a = rho_air * volume * cp_air
                # Mass capacitance C_m (J/K)
                c_m = area * float(type_gains.get("cm_per_sqm", 70000.0))
                # Envelope UA (W/K) -> R_ao (K/W)
                ua_total = area * float(type_gains.get("ua_per_sqm", 2.2))
                r_ao = 1.0 / max(1e-4, ua_total)
                # Air-mass coupling (W/K) -> R_am (K/W)
                h_am_total = area * float(type_gains.get("ram_coupling_w_per_sqm", 6.5))
                r_am = 1.0 / max(1e-4, h_am_total)

                # Total rated sensible cooling capacity (W)
                tot_rated_kw = sum(u.rated_kw for u in units)
                rated_sens_w = tot_rated_kw * 1000.0 * shr

                # Design conditions and coincident diversity factors (ASSUMPTION)
                design_conds = phys_cfg.get("design_conditions", {})
                t_design_out = float(design_conds.get("outdoor_design_temp_c", 38.0))
                f_person = float(design_conds.get("person_diversity_factor", 0.85))
                f_lighting = float(design_conds.get("lighting_diversity_factor", 0.85))
                f_equip = float(design_conds.get("equipment_diversity_factor", 0.80))

                cap = int(r_raw["capacity"])
                person_sens_w = float(type_gains.get("person_sensible_w", 70.0))
                lighting_w = area * float(type_gains.get("lighting_w_per_sqm", 10.5)) * f_lighting
                equip_w = float(type_gains.get("equipment_w", 500.0)) * f_equip if room_type != "server_room" else float(type_gains.get("equipment_w", 7200.0))
                env_gain_w = ua_total * (t_design_out - float(r_raw["target_temp_c"]))
                design_load_w = (cap * person_sens_w * f_person) + lighting_w + equip_w + env_gain_w

                # Sizing classification: margin = (Rated - Design) / Design * 100
                # Deliberate exceptions: exactly 1 undersized (< 0%), exactly 2 marginal (0% to 10%), server room ok (>35%), and 14 ok (15% to 35%)
                margin = ((rated_sens_w - design_load_w) / design_load_w) * 100.0
                if margin < 0.0:
                    sizing_status = "undersized"
                elif 0.0 <= margin <= 10.0:
                    sizing_status = "marginal"
                else:
                    sizing_status = "ok"

                room = Room(
                    id=r_raw["id"],
                    building=b_raw["name"],
                    name=r_raw["name"],
                    room_type=room_type,
                    area_sqm=area,
                    height_m=height,
                    capacity=cap,
                    target_temp_c=float(r_raw["target_temp_c"]),
                    min_temp_c=float(r_raw["min_temp_c"]),
                    max_temp_c=float(r_raw["max_temp_c"]),
                    is_critical=bool(r_raw.get("is_critical", False)),
                    thermal_multiplier=float(r_raw.get("thermal_multiplier", 1.0)),
                    c_a=c_a,
                    c_m=c_m,
                    r_ao=r_ao,
                    r_am=r_am,
                    design_load_w=round(design_load_w, 1),
                    rated_sensible_cooling_w=round(rated_sens_w, 1),
                    sizing_status=sizing_status,
                    sizing_margin_pct=round(margin, 1),
                    units=units
                )
                rooms.append(room)

            building = Building(
                id=b_raw["id"],
                name=b_raw["name"],
                archetype_building_id=int(b_raw["archetype_building_id"]),
                rooms=rooms
            )
            buildings.append(building)

        schedules = []
        for s_raw in rooms_data.get("schedules", []):
            days = s_raw["day_of_week"]
            if isinstance(days, int):
                days = [days]
            for day in days:
                schedules.append(
                    TimetableEntry(
                        room_id=s_raw["room_id"],
                        day_of_week=day,
                        start_time_str=s_raw["start_time"],
                        end_time_str=s_raw["end_time"],
                        activity_name=s_raw.get("activity_name", "Class"),
                        expected_headcount=int(s_raw.get("expected_headcount", 20))
                    )
                )

        special_events = [
            SpecialEvent(
                id=e["id"],
                room_id=e["room_id"],
                event_date=e["date"],
                start_time_str=e["start_time"],
                end_time_str=e["end_time"],
                activity_name=e["activity_name"],
                expected_headcount=int(e["expected_headcount"])
            )
            for e in rooms_data.get("special_events", [])
        ]

        holidays = [str(h) for h in rooms_data.get("holidays", [])]

        return cls(buildings, schedules, special_events, holidays)

    def is_holiday(self, dt: datetime) -> bool:
        return dt.strftime("%Y-%m-%d") in self.holidays

    def get_room(self, room_id: str) -> Room | None:
        return self._rooms_by_id.get(room_id)

    def get_building_for_room(self, room_id: str) -> Building | None:
        return self._building_by_room_id.get(room_id)

    def get_active_schedule(self, room_id: str, dt: datetime) -> dict[str, Any] | None:
        date_str = dt.strftime("%Y-%m-%d")
        time_minutes = dt.hour * 60 + dt.minute

        if self.is_holiday(dt):
            return None

        for ev in self.special_events:
            if ev.room_id == room_id and ev.event_date == date_str:
                parts_s = ev.start_time_str.split(":")
                ev_start_min = int(parts_s[0]) * 60 + int(parts_s[1])
                parts_e = ev.end_time_str.split(":")
                ev_end_min = int(parts_e[0]) * 60 + int(parts_e[1])
                if ev_start_min <= time_minutes < ev_end_min:
                    return {
                        "is_scheduled": True,
                        "activity_name": ev.activity_name,
                        "expected_headcount": ev.expected_headcount,
                        "start_minute": ev_start_min,
                        "end_minute": ev_end_min,
                        "is_special_event": True
                    }

        dow = dt.weekday()
        for s in self.schedules:
            if s.room_id == room_id and s.day_of_week == dow:
                if s.start_minute <= time_minutes < s.end_minute:
                    return {
                        "is_scheduled": True,
                        "activity_name": s.activity_name,
                        "expected_headcount": s.expected_headcount,
                        "start_minute": s.start_minute,
                        "end_minute": s.end_minute,
                        "is_special_event": False
                    }
        return None

    @property
    def all_rooms(self) -> list[Room]:
        return list(self._rooms_by_id.values())

    @property
    def all_units(self) -> list[ACUnit]:
        return [u for u, _ in self._units_by_id.values()]
