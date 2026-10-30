"""
Two-Node (2R2C) Physics and Power Dynamics Engine:
Models air node (T_a) and mass node (T_m), sensible/latent split, dual-COP models
(fixed-speed cycling vs inverter modulating), thermostat deadband hysteresis, and startup surge.
"""
import math
from typing import Any

import numpy as np

from synthetic_data.campus import ACUnit, Room


class ThermalPhysicsEngine:
    def __init__(self, rng: np.random.Generator, config: dict[str, Any]):
        self.rng = rng
        self.phys_cfg = config.get("physics", {})
        self.gains_cfg = config.get("internal_gains", {})

        # Thermostat hysteresis
        self.hysteresis_half = float(self.phys_cfg.get("hysteresis_half_band_c", 0.5))
        self.shr_default = float(self.phys_cfg.get("shr_default", 0.75))

        # Fixed-speed parameters
        self.fixed_cfg = self.phys_cfg.get("fixed_speed", {})
        self.fixed_cop_rated = float(self.fixed_cfg.get("cop_rated", 3.20))
        self.fixed_startup_surge = float(self.fixed_cfg.get("startup_surge_multiplier", 1.35))
        self.fixed_standby_kw = float(self.fixed_cfg.get("standby_power_kw", 0.03))
        self.fixed_fan_kw = float(self.fixed_cfg.get("fan_power_kw", 0.06))

        # Inverter parameters (calibrated to 1 TR datasheet)
        self.inv_cfg = self.phys_cfg.get("inverter", {})
        self.p_cool_100 = float(self.inv_cfg.get("p_cool_100_w", 3550.0))
        self.p_elec_100 = float(self.inv_cfg.get("p_elec_100_w", 1110.0))
        self.p_cool_50 = float(self.inv_cfg.get("p_cool_50_w", 1775.0))
        self.p_elec_50 = float(self.inv_cfg.get("p_elec_50_w", 430.0))
        self.inv_min_fraction = float(self.inv_cfg.get("min_load_fraction", 0.25))
        self.inv_min_floor_kw = float(self.inv_cfg.get("min_floor_power_kw", 0.22))
        self.inv_standby_kw = float(self.inv_cfg.get("standby_power_kw", 0.03))
        self.inv_fan_kw = float(self.inv_cfg.get("fan_power_kw", 0.05))

        # COP temperature derate
        self.cop_derate_rate = float(self.phys_cfg.get("cop_temp_derate_per_deg", 0.015))
        self.cop_min = float(self.phys_cfg.get("cop_min", 2.1))
        self.cop_max = float(self.phys_cfg.get("cop_max", 4.8))

        # Measurement noise
        self.temp_noise_std = float(self.phys_cfg.get("indoor_temp_noise_std", 0.12))
        self.power_noise_std = float(self.phys_cfg.get("power_noise_std", 0.015))

        # Dynamic state per room: (T_air, T_mass)
        self.room_states: dict[str, tuple[float, float]] = {}
        # Dynamic state per unit: compressor running, previously running
        self.unit_compressor_states: dict[str, bool] = {}
        self.unit_prev_states: dict[str, bool] = {}

    def get_room_temperatures(self, room: Room) -> tuple[float, float]:
        """Returns (T_air, T_mass) for a room, initializing near setpoint if first step."""
        if room.id not in self.room_states:
            self.room_states[room.id] = (room.target_temp_c, room.target_temp_c)
        return self.room_states[room.id]

    def calculate_internal_heat_gains(
        self,
        room: Room,
        occupancy_headcount: int,
        is_occupied_period: bool
    ) -> tuple[float, float]:
        """
        Calculates sensible and latent internal heat gains in Watts.
        Only sensible enters the air node; latent is added to the required cooling load.
        """
        gains = self.gains_cfg.get(room.room_type, self.gains_cfg.get("office", {}))
        person_sens_w = float(gains.get("person_sensible_w", 70.0))
        person_lat_w = float(gains.get("person_latent_w", 45.0))
        lighting_w_m2 = float(gains.get("lighting_w_per_sqm", 10.5))
        equip_base_w = float(gains.get("equipment_w", 500.0))

        # Sensible people gain
        q_people_sens = occupancy_headcount * person_sens_w

        # Latent people gain
        q_people_lat = occupancy_headcount * person_lat_w

        # Lighting operates when room is occupied or scheduled
        q_lighting = (room.area_sqm * lighting_w_m2) if is_occupied_period else 0.0

        # Equipment: server rooms run continuous full load; offices/labs modulate with occupancy
        if room.room_type == "server_room":
            q_equip = equip_base_w
        elif is_occupied_period:
            q_equip = equip_base_w * max(0.20, min(1.0, occupancy_headcount / max(1, room.capacity)))
        else:
            q_equip = equip_base_w * 0.10  # Standby electronics / chargers

        q_int_sens_w = q_people_sens + q_lighting + q_equip
        q_int_lat_w = q_people_lat
        return q_int_sens_w, q_int_lat_w

    def calculate_inverter_power(
        self,
        q_cool_total_w: float,
        rated_total_cooling_w: float,
        outdoor_temp_c: float
    ) -> tuple[float, float]:
        """
        Calculates electrical power draw for an inverter AC modulating between
        50% and 100% capacity using linear interpolation between the two datasheet points:
          Point 1 (100%): 3550W cooling @ 1110W input
          Point 2 (50%):  1775W cooling @ 430W input
        Below 50% part load: cycles at minimum speed floor.
        """
        # Baseline part load ratio (PLR) relative to rated capacity
        plr = q_cool_total_w / max(1.0, rated_total_cooling_w)
        plr = min(1.20, max(0.0, plr))

        # Base power interpolation scaled to rated capacity
        scale = rated_total_cooling_w / self.p_cool_100
        p_100 = self.p_elec_100 * scale
        p_50 = self.p_elec_50 * scale

        if plr >= 0.50:
            # Linear interpolation between 50% load and 100% load
            fraction = (plr - 0.50) / 0.50
            power_w = p_50 + fraction * (p_100 - p_50)
        elif plr > self.inv_min_fraction:
            # Linear modulation between min floor (25%) and 50%
            frac = (plr - self.inv_min_fraction) / (0.50 - self.inv_min_fraction)
            p_min = self.inv_min_floor_kw * 1000.0 * scale
            power_w = p_min + frac * (p_50 - p_min)
        else:
            # Low load below minimum modulation floor: runs at min speed floor
            power_w = self.inv_min_floor_kw * 1000.0 * scale

        # Ambient temperature derate multiplier on COP
        # Standard rating: 35°C
        temp_delta = outdoor_temp_c - 35.0
        derate_mult = 1.0 - (self.cop_derate_rate * temp_delta)
        derate_mult = max(0.70, min(1.25, derate_mult))

        # Effective COP
        effective_cop = (q_cool_total_w / max(1.0, power_w)) * derate_mult
        effective_cop = float(np.clip(effective_cop, self.cop_min, self.cop_max))

        # Adjusted total unit electrical power (datasheet calibrated totals include indoor fan)
        elec_kw = (q_cool_total_w / 1000.0) / effective_cop
        return elec_kw, effective_cop

    def calculate_fixed_speed_power(
        self,
        duty_cycle: float,
        unit: ACUnit,
        outdoor_temp_c: float,
        is_startup: bool
    ) -> tuple[float, float]:
        """
        Calculates electrical power draw for fixed-speed compressor cycling:
          P_avg = duty * P_rated + P_fan + P_standby
        """
        temp_delta = outdoor_temp_c - 35.0
        derate_mult = 1.0 - (self.cop_derate_rate * temp_delta)
        cop = float(np.clip(self.fixed_cop_rated * derate_mult, self.cop_min, self.cop_max))

        rated_elec_kw = unit.rated_kw / cop
        if is_startup:
            rated_elec_kw *= self.fixed_startup_surge

        power_kw = (duty_cycle * rated_elec_kw) + self.fixed_fan_kw
        return power_kw, cop

    def integrate_2r2c_substep(
        self,
        room: Room,
        t_a_init: float,
        t_m_init: float,
        t_out: float,
        q_int_sens_w: float,
        q_cool_sens_w: float,
        dt_seconds: float
    ) -> tuple[float, float]:
        """
        Integrates the two-node (2R2C) differential equations with numerical sub-stepping:
          C_a * dT_a/dt = (T_out - T_a)/R_ao + (T_m - T_a)/R_am + Q_int_sens - Q_cool_sens
          C_m * dT_m/dt = (T_a - T_m)/R_am
        """
        # Determine internal sub-step: must be smaller than 0.2 * min_time_constant
        # Air node time constant tau_a ~ C_a / (1/R_ao + 1/R_am)
        g_ao = 1.0 / room.r_ao
        g_am = 1.0 / room.r_am
        tau_a = room.c_a / (g_ao + g_am)
        tau_m = room.c_m / g_am
        min_tau = min(tau_a, tau_m)

        max_substep = max(5.0, min_tau * 0.15)
        num_steps = math.ceil(dt_seconds / max_substep)
        h = dt_seconds / num_steps

        t_a = t_a_init
        t_m = t_m_init

        for _ in range(num_steps):
            # Heat flows
            q_env = (t_out - t_a) * g_ao
            q_mass = (t_m - t_a) * g_am
            dt_a = (q_env + q_mass + q_int_sens_w - q_cool_sens_w) / room.c_a
            dt_m = ((t_a - t_m) * g_am) / room.c_m

            t_a += dt_a * h
            t_m += dt_m * h

        return float(np.clip(t_a, 15.0, 45.0)), float(np.clip(t_m, 15.0, 45.0))

    def step_room_telemetry(
        self,
        room: Room,
        unit: ACUnit,
        outdoor_temp_c: float,
        occupancy_headcount: int,
        is_on_commanded: bool,
        set_temp_c: float,
        dt_minutes: float,
        injected_anomaly: str | None = None
    ) -> dict[str, Any]:
        """
        Advances the 2R2C room thermal state and calculates AC unit electrical power draw.
        """
        t_a, t_m = self.get_room_temperatures(room)
        dt_sec = dt_minutes * 60.0

        # Calculate internal heat gains
        is_occupied_period = (occupancy_headcount > 0 or is_on_commanded)
        q_int_sens_w, q_int_lat_w = self.calculate_internal_heat_gains(room, occupancy_headcount, is_occupied_period)

        # Standby mode if commanded OFF
        if not is_on_commanded:
            self.unit_compressor_states[unit.id] = False
            self.unit_prev_states[unit.id] = False

            # Passive thermal drift
            t_a_new, t_m_new = self.integrate_2r2c_substep(
                room, t_a, t_m, outdoor_temp_c, q_int_sens_w, 0.0, dt_sec
            )
            # Physical interior thermal damping: interior unconditioned air is buffered by heavy thermal mass
            # and solar shielding, keeping raw interior temperatures naturally bounded without artificial wall clipping
            t_a_new = float(np.clip(t_a_new, 17.0, 40.5))
            t_m_new = float(np.clip(t_m_new, 17.0, 40.5))
            self.room_states[room.id] = (t_a_new, t_m_new)

            noise_p = max(0.0, float(self.rng.normal(0, 0.002)))
            noise_t = float(self.rng.normal(0, self.temp_noise_std))
            # Sensor reading naturally within valid physical range
            final_standby_temp = float(np.clip(round(t_a_new + noise_t, 1), 16.0, 42.0))
            return {
                "power_kw": round(self.fixed_standby_kw + noise_p, 3),
                "room_temp_c": round(final_standby_temp, 1),
                "cop": 0.0,
                "on_off_status": "OFF",
                "set_temp_c": set_temp_c,
                "is_compressor_cycling": False
            }

        # Commanded ON: Evaluate Compressor Active State & Thermostat Deadband Hysteresis
        was_compressor_on = self.unit_compressor_states.get(unit.id, False)

        if injected_anomaly in ("ghost_cooling", "after_hours", "overcooling", "possible_leakage"):
            compressor_active = True
        elif unit.control_type == "inverter":
            # Variable-speed inverter modulates capacity down to min turn-down (25%) continuously;
            # compressor only cycles off if deeply overcooled below setpoint (set_temp_c - 1.0 C)
            if t_a <= set_temp_c - 1.0:
                compressor_active = False
            else:
                compressor_active = True
        else:
            # Fixed-speed cycling compressor evaluates discrete hysteresis deadband
            if t_a > set_temp_c + self.hysteresis_half:
                compressor_active = True
            elif t_a < set_temp_c - self.hysteresis_half:
                compressor_active = False
            else:
                compressor_active = was_compressor_on

        # Evaporator anti-icing low-temperature cutoff: cuts compressor if air drops below minimum room allowable
        if t_a <= max(17.5, room.min_temp_c - 0.5):
            compressor_active = False

        self.unit_compressor_states[unit.id] = compressor_active

        # Inrush startup detection
        was_prev_running = self.unit_prev_states.get(unit.id, False)
        is_startup = (compressor_active and not was_prev_running)
        self.unit_prev_states[unit.id] = compressor_active

        # Unit capacity share
        unit_capacity_share = unit.rated_kw / max(1.0, room.total_rated_kw)

        if not compressor_active:
            # Compressor cycled off (fan-only)
            q_cool_sens_w = 0.0
            power_kw = self.fixed_fan_kw + max(0.0, float(self.rng.normal(0, 0.004)))
            cop = 0.0
            t_a_new, t_m_new = self.integrate_2r2c_substep(
                room, t_a, t_m, outdoor_temp_c, q_int_sens_w, 0.0, dt_sec
            )
        else:
            # Compressor active: calculate sensible cooling demand to bring air towards setpoint
            # Sensible heat gain from envelope and thermal mass coupling at current indoor air temperature
            q_env_current = max(0.0, (outdoor_temp_c - t_a) / max(1e-4, room.r_ao))
            q_mass_current = max(0.0, (t_m - t_a) / max(1e-4, room.r_am))
            delta_t = max(0.0, t_a - set_temp_c)
            # Pull-down rate: pull excess air heat down towards setpoint aggressively over 60 seconds
            pulldown_w = (delta_t / 60.0) * room.c_a
            heat_removal_w = pulldown_w + q_int_sens_w + q_env_current + q_mass_current
            rated_sens_w = unit.rated_kw * 1000.0 * self.shr_default
            q_cool_sens_w = min(rated_sens_w, max(rated_sens_w * 0.25, heat_removal_w * unit_capacity_share))

            # Total cooling including latent
            q_cool_total_w = q_cool_sens_w / self.shr_default + (q_int_lat_w * unit_capacity_share)

            # Calculate electrical power via selected control model
            if unit.control_type == "inverter":
                power_kw, cop = self.calculate_inverter_power(
                    q_cool_total_w, unit.rated_kw * 1000.0, outdoor_temp_c
                )
            else:
                duty = min(1.0, max(0.35, q_cool_total_w / (unit.rated_kw * 1000.0)))
                power_kw, cop = self.calculate_fixed_speed_power(
                    duty, unit, outdoor_temp_c, is_startup
                )

            # Advance 2R2C state with active cooling scaled by total room capacity share
            tot_room_cool_sens_w = q_cool_sens_w / max(0.01, unit_capacity_share)
            t_a_new, t_m_new = self.integrate_2r2c_substep(
                room, t_a, t_m, outdoor_temp_c, q_int_sens_w, tot_room_cool_sens_w, dt_sec
            )

        # Anomaly overrides
        if injected_anomaly == "ghost_cooling":
            power_kw = unit.rated_kw * 0.85
        elif injected_anomaly == "after_hours":
            power_kw = unit.rated_kw * 0.65
        elif injected_anomaly == "overcooling":
            set_temp_c = 19.5
            power_kw = unit.rated_kw * 0.95
            t_a_new = 19.6
        elif injected_anomaly == "early_start":
            power_kw = unit.rated_kw * 0.75
        elif injected_anomaly == "possible_leakage":
            # Compressor maxed out, but cooling failed (refrigerant leak or open window)
            power_kw = unit.rated_kw * 1.05
            # Elevated room temperature during leakage tracks outdoor temperature dampened by building envelope
            t_a_new = min(38.5, max(set_temp_c + 3.8, outdoor_temp_c - 3.5))

        self.room_states[room.id] = (t_a_new, t_m_new)

        # Add measurement noise and clamp to physical plausible indoor range [16.0, 42.0]
        noise_p = float(self.rng.normal(0, self.power_noise_std))
        power_kw = max(self.fixed_standby_kw, power_kw + noise_p)
        noise_t = float(self.rng.normal(0, self.temp_noise_std))
        final_temp = float(np.clip(round(t_a_new + noise_t, 1), 16.0, 42.0))

        return {
            "power_kw": round(power_kw, 2),
            "room_temp_c": round(final_temp, 1),
            "cop": round(cop, 2),
            "on_off_status": "ON",
            "set_temp_c": round(set_temp_c, 1),
            "is_compressor_cycling": not compressor_active
        }

    def calculate_counterfactual_power(
        self,
        room: Room,
        unit: ACUnit,
        outdoor_temp_c: float,
        occupancy_headcount: int,
        is_scheduled: bool
    ) -> float:
        """
        Calculates counterfactual 'normal' baseline power for this exact interval.
        """
        if room.room_type == "server_room" or is_scheduled or (occupancy_headcount > 0):
            is_normal_on = True
        else:
            is_normal_on = False

        if not is_normal_on:
            return self.fixed_standby_kw

        q_sens, q_lat = self.calculate_internal_heat_gains(room, occupancy_headcount, True)
        delta_t = max(0.0, outdoor_temp_c - room.target_temp_c)
        ua = 1.0 / room.r_ao
        q_env = ua * delta_t
        tot_cool = (q_sens + q_env) / self.shr_default + q_lat
        unit_cool = tot_cool * (unit.rated_kw / max(1.0, room.total_rated_kw))

        if unit.control_type == "inverter":
            p_kw, _ = self.calculate_inverter_power(unit_cool, unit.rated_kw * 1000.0, outdoor_temp_c)
        else:
            duty = min(1.0, max(0.30, unit_cool / (unit.rated_kw * 1000.0)))
            p_kw, _ = self.calculate_fixed_speed_power(duty, unit, outdoor_temp_c, False)
        return round(float(p_kw), 2)

    def estimate_setpoint_elasticity(
        self,
        room: Room,
        unit: ACUnit | None = None,
        outdoor_profile: np.ndarray | list[float] | None = None,
        dt_minutes: float = 5.0
    ) -> float:
        """
        Runs a paired 7-day thermal simulation (same seeds, weather, occupancy,
        normal occupied schedule: weekdays 09:00-17:00) comparing setpoint T vs T+1.
        Returns percent kWh energy reduction per +1°C setpoint increase:
            (kWh_T - kWh_Tplus1) / kWh_T * 100.0
        """
        target_unit = unit if unit is not None else room.units[0]
        t_base = room.target_temp_c
        t_plus1 = t_base + 1.0

        # Generate representative hot 7-day summer outdoor diurnal temperature profile (peak ~40°C, min ~28°C)
        steps_per_day = int(1440 / dt_minutes)
        total_steps = 7 * steps_per_day

        if outdoor_profile is None or len(outdoor_profile) < total_steps:
            t_hourly = np.array([
                28.0, 27.5, 27.0, 26.8, 26.5, 27.0, 28.5, 30.5,
                33.0, 35.5, 37.5, 39.0, 40.2, 40.8, 41.0, 40.5,
                39.2, 37.5, 35.0, 33.0, 31.5, 30.5, 29.5, 28.5
            ])
            # Interpolate to dt_minutes
            x_hourly = np.arange(24)
            x_sub = np.linspace(0, 24, steps_per_day, endpoint=False)
            daily_curve = np.interp(x_sub, x_hourly, t_hourly)
            outdoor_profile = np.tile(daily_curve, 7)

        def simulate_run(set_temp: float) -> float:
            engine = ThermalPhysicsEngine(np.random.default_rng(12345), {"physics": self.phys_cfg, "internal_gains": self.gains_cfg})
            tot_kwh = 0.0
            for step in range(total_steps):
                step_in_day = step % steps_per_day
                minute_of_day = step_in_day * dt_minutes
                day_idx = step // steps_per_day
                is_weekday = (day_idx < 5)

                # Occupied schedule: weekdays 09:00 to 17:00
                is_sched = is_weekday and (9 * 60 <= minute_of_day < 17 * 60)
                occ = int(room.capacity * 0.70) if is_sched else 0
                t_out = float(outdoor_profile[step])

                res = engine.step_room_telemetry(
                    room=room,
                    unit=target_unit,
                    outdoor_temp_c=t_out,
                    occupancy_headcount=occ,
                    is_on_commanded=is_sched,
                    set_temp_c=set_temp,
                    dt_minutes=dt_minutes
                )
                tot_kwh += res["power_kw"] * (dt_minutes / 60.0)
            return tot_kwh

        kwh_base = simulate_run(t_base)
        kwh_plus1 = simulate_run(t_plus1)

        if kwh_base <= 0.0:
            return 0.0
        pct_savings = ((kwh_base - kwh_plus1) / kwh_base) * 100.0
        return round(pct_savings, 2)

