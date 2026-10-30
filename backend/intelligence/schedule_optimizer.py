"""
Schedule Optimizer Service:
Core intelligence engine for optimal pre-cool lead, shut-off timing,
gap merging (compressor protection), comfort band validation,
and monthly cost savings calculation.

Follows physical 1R1C thermal dynamics and ASHRAE 55 comfort guidelines.
"""
import math
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from domain.ac_models import (
    RoomModel, ACUnitModel, ScheduleModel, TariffModel, WasteEventModel, ProposalModel
)


def format_inr_compact(amount: float) -> str:
    """Formats an INR amount using Indian compact notation (₹k, ₹L)."""
    if amount >= 100000:
        return f"₹{amount / 100000:.1f}L"
    elif amount >= 1000:
        return f"₹{amount / 1000:.1f}k"
    else:
        return f"₹{int(round(amount))}"


class ScheduleOptimizerService:
    def __init__(
        self,
        default_tariff: float = 9.20,
        min_lead_min: int = 10,
        max_lead_min: int = 45,
        shutoff_grace_min: int = 10,
        min_off_gap_min: int = 90,
        elasticity_k: float = 0.04,  # 4% per °C
        weeks_per_month: float = 4.33
    ):
        self.default_tariff = default_tariff
        self.min_lead_min = min_lead_min
        self.max_lead_min = max_lead_min
        self.shutoff_grace_min = shutoff_grace_min
        self.min_off_gap_min = min_off_gap_min
        self.elasticity_k = elasticity_k
        self.weeks_per_month = weeks_per_month

    def calculate_precool_lead(
        self,
        T0: float,
        Tout: float,
        Ttarget: float,
        R: float = 3.5,        # °C / kW
        C: float = 6.114,      # kWh / °C -> tau = R*C = 21.4 minutes
        Q_int: float = 0.5,    # kW internal heat gain
        Q_cool_sens: float = 4.25  # kW sensible cooling capacity
    ) -> Tuple[int, str, float]:
        """
        R1: Computes pull-down pre-cool lead using the 1R1C lumped capacitance model:
            t = tau * ln((T0 - Teq) / (Ttarget - Teq))
            tau = R * C (in minutes)
            Teq = Tout + R * (Q_int - Q_cool_sens)
        Clamped to [min_lead, max_lead] and rounded UP to next 5 minutes.
        Returns: (lead_minutes, warning_or_ok, Teq)
        """
        tau = R * C  # 21.4 minutes
        Teq = Tout + R * (Q_int - Q_cool_sens)

        if Teq >= Ttarget:
            return self.max_lead_min, "Target unreachable with current ambient and cooling capacity", Teq

        if T0 <= Ttarget:
            return self.min_lead_min, "ok", Teq

        num = T0 - Teq
        den = Ttarget - Teq
        if den <= 0:
            return self.max_lead_min, "Target unreachable", Teq

        t = tau * math.log(num / den)
        # Clamp to [min_lead, max_lead]
        clamped = max(float(self.min_lead_min), min(float(self.max_lead_min), t))
        # Round up to 5 minutes
        rounded = int(math.ceil(clamped / 5.0) * 5)
        rounded = max(self.min_lead_min, min(self.max_lead_min, rounded))
        return rounded, "ok", Teq

    def time_to_minutes(self, t_str: str) -> int:
        """Converts HH:MM or HH:MM:SS to minutes from midnight."""
        parts = t_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    def minutes_to_time(self, mins: int) -> str:
        """Converts minutes from midnight to HH:MM."""
        h = (mins // 60) % 24
        m = mins % 60
        return f"{h:02d}:{m:02d}"

    def build_daily_recommended_runs(
        self,
        timetable_blocks: List[Dict[str, Any]],
        precool_lead_min: int,
        shutoff_grace_min: int
    ) -> List[Dict[str, Any]]:
        """
        R2 & R3: Builds recommended runs from daily timetable blocks.
        Applies shut-off = class_end + grace (+10 min).
        Applies min off time (compressor protection): merges sessions if gap < min_off_gap (90 min),
        and shades the gap as kept on.
        """
        if not timetable_blocks:
            return []

        # Sort timetable blocks by start_time
        sorted_blocks = sorted(timetable_blocks, key=lambda b: self.time_to_minutes(b["start_time"]))

        # Group blocks that have gap < min_off_gap_min
        groups: List[List[Dict[str, Any]]] = []
        current_group = [sorted_blocks[0]]

        for i in range(1, len(sorted_blocks)):
            prev_end = self.time_to_minutes(sorted_blocks[i - 1]["end_time"])
            curr_start = self.time_to_minutes(sorted_blocks[i]["start_time"])
            gap = curr_start - prev_end

            if gap < self.min_off_gap_min:
                # Merge into same run
                current_group.append(sorted_blocks[i])
            else:
                groups.append(current_group)
                current_group = [sorted_blocks[i]]
        groups.append(current_group)

        # Build run objects
        runs = []
        for g in groups:
            first_start = self.time_to_minutes(g[0]["start_time"])
            last_end = self.time_to_minutes(g[-1]["end_time"])

            run_start_mins = max(5 * 60, first_start - precool_lead_min)
            run_end_mins = min(23 * 60, last_end + shutoff_grace_min)

            kept_on_gaps = []
            for j in range(len(g) - 1):
                gap_st = g[j]["end_time"][:5]
                gap_et = g[j + 1]["start_time"][:5]
                kept_on_gaps.append({
                    "start_time": gap_st,
                    "end_time": gap_et,
                    "duration_min": self.time_to_minutes(gap_et) - self.time_to_minutes(gap_st)
                })

            runs.append({
                "start_time": self.minutes_to_time(run_start_mins),
                "end_time": self.minutes_to_time(run_end_mins),
                "duration_hours": round((run_end_mins - run_start_mins) / 60.0, 2),
                "precool_lead_min": precool_lead_min,
                "shutoff_grace_min": shutoff_grace_min,
                "is_merged": len(g) > 1,
                "kept_on_gaps": kept_on_gaps,
                "covered_sessions": [
                    {
                        "title": b.get("activity_name", "Class"),
                        "start_time": b["start_time"][:5],
                        "end_time": b["end_time"][:5]
                    }
                    for b in g
                ]
            })

        return runs

    def compute_savings(
        self,
        timer_hours_per_day: Dict[int, float],
        recommended_hours_per_day: Dict[int, float],
        setpoint: float,
        baseline_setpoint: float = 24.0,
        baseline_p_on_kw: float = 4.65,
        band_low_kw: float = 4.22,
        band_high_kw: float = 5.08,
        tariff: float = 9.20
    ) -> Dict[str, Any]:
        """
        Computes monthly savings range:
        saved_hours_week = sum over days (timer_on_hours - recommended_on_hours)
        kWh_saved_month = saved_hours_week * weeks_per_month (4.33) * P_on_kw
        setpoint effect: multiply P_on_kw by (1 - k)^(setpoint_delta) when setpoint > baseline_setpoint
        cost = kWh * tariff
        range: low/high from band_low / band_high
        """
        saved_hours_by_day = {}
        for dow in range(7):
            t_hrs = timer_hours_per_day.get(dow, 0.0)
            r_hrs = recommended_hours_per_day.get(dow, 0.0)
            saved_hours_by_day[dow] = max(0.0, round(t_hrs - r_hrs, 2))

        saved_hours_week = sum(saved_hours_by_day.values())
        hours_saved_month = round(saved_hours_week * self.weeks_per_month, 2)

        # Setpoint elasticity effect
        setpoint_delta = max(0.0, setpoint - baseline_setpoint)
        elasticity_factor = (1.0 - self.elasticity_k) ** setpoint_delta

        eff_p_kw = baseline_p_on_kw * elasticity_factor
        eff_low_kw = band_low_kw * elasticity_factor
        eff_high_kw = band_high_kw * elasticity_factor

        kwh_est = round(hours_saved_month * eff_p_kw, 1)
        kwh_low = round(hours_saved_month * eff_low_kw, 1)
        kwh_high = round(hours_saved_month * eff_high_kw, 1)

        cost_est = round(kwh_est * tariff, 2)
        cost_low = round(kwh_low * tariff, 2)
        cost_high = round(kwh_high * tariff, 2)

        formatted_range = f"{format_inr_compact(cost_low)} – {format_inr_compact(cost_high)}"

        return {
            "saved_hours_week": round(saved_hours_week, 1),
            "hours_saved_month": round(hours_saved_month, 2),
            "saved_hours_by_day": saved_hours_by_day,
            "setpoint_delta": round(setpoint_delta, 1),
            "elasticity_factor": round(elasticity_factor, 4),
            "kwh_saved_month": {
                "est": kwh_est,
                "low": kwh_low,
                "high": kwh_high
            },
            "cost_saved_month": {
                "est": cost_est,
                "low": cost_low,
                "high": cost_high,
                "formatted_range": formatted_range
            }
        }

    def validate_schedule_bars(
        self,
        room: RoomModel,
        timetable_by_day: Dict[int, List[Dict[str, Any]]],
        bars_by_day: Dict[int, List[Dict[str, Any]]],
        setpoint: float,
        calculated_lead_min: int
    ) -> Dict[str, Any]:
        """
        R5: Comfort and safety validation.
        Returns:
            status: 'ok' | 'warning' | 'blocked'
            issues: list of issue objects { day, type, level, message }
        """
        issues = []
        overall_status = "ok"

        # 1. Setpoint check
        if setpoint < room.min_temp_c or setpoint > room.max_temp_c:
            overall_status = "blocked"
            issues.append({
                "type": "setpoint_out_of_bounds",
                "level": "blocked",
                "message": f"Setpoint {setpoint} °C is outside allowed comfort range ({room.min_temp_c}–{room.max_temp_c} °C)."
            })

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for dow in range(7):
            day_sessions = timetable_by_day.get(dow, [])
            day_bars = bars_by_day.get(dow, [])
            d_name = day_names[dow]

            # Check overlap between bars
            sorted_bars = sorted(day_bars, key=lambda b: self.time_to_minutes(b["start_time"]))
            for i in range(len(sorted_bars) - 1):
                b1_end = self.time_to_minutes(sorted_bars[i]["end_time"])
                b2_start = self.time_to_minutes(sorted_bars[i + 1]["start_time"])
                if b2_start < b1_end:
                    overall_status = "blocked"
                    issues.append({
                        "day": dow,
                        "level": "blocked",
                        "message": f"{d_name}: Bars cannot cross or overlap each other."
                    })
                elif (b2_start - b1_end) < 30:
                    if overall_status != "blocked":
                        overall_status = "warning"
                    issues.append({
                        "day": dow,
                        "level": "warning",
                        "message": f"{d_name}: Gap between runs is under 30 minutes. Compressor may cycle rapidly."
                    })

            for bar in day_bars:
                st = self.time_to_minutes(bar["start_time"])
                et = self.time_to_minutes(bar["end_time"])
                duration = et - st

                # Min duration constraint
                if duration < 30:
                    overall_status = "blocked"
                    issues.append({
                        "day": dow,
                        "level": "blocked",
                        "message": f"{d_name}: Run duration must be at least 30 minutes ({bar['start_time']}–{bar['end_time']})."
                    })

                # Boundary constraints (05:00 - 23:00)
                if st < 5 * 60 or et > 23 * 60:
                    overall_status = "blocked"
                    issues.append({
                        "day": dow,
                        "level": "blocked",
                        "message": f"{d_name}: Run cannot be scheduled outside 05:00–23:00."
                    })

            # Check coverage of timetable blocks
            for sess in day_sessions:
                s_st = self.time_to_minutes(sess["start_time"])
                s_et = self.time_to_minutes(sess["end_time"])

                # Find bar that covers this session
                covering = [b for b in day_bars if self.time_to_minutes(b["start_time"]) <= s_st and self.time_to_minutes(b["end_time"]) >= s_et]

                if not covering:
                    # Check if partly covered
                    partly = [b for b in day_bars if not (self.time_to_minutes(b["end_time"]) <= s_st or self.time_to_minutes(b["start_time"]) >= s_et)]
                    if not partly:
                        overall_status = "blocked"
                        issues.append({
                            "day": dow,
                            "level": "blocked",
                            "message": f"{d_name}: Scheduled session ({sess['start_time'][:5]}–{sess['end_time'][:5]}) has no AC coverage."
                        })
                    else:
                        lead = s_st - self.time_to_minutes(partly[0]["start_time"])
                        if lead < calculated_lead_min:
                            if overall_status != "blocked":
                                overall_status = "warning"
                            issues.append({
                                "day": dow,
                                "level": "warning",
                                "message": f"{d_name}: Lead shorter than pull-down time ({calculated_lead_min} min): room may be warm at start."
                            })
                else:
                    lead = s_st - self.time_to_minutes(covering[0]["start_time"])
                    if lead < calculated_lead_min:
                        if overall_status != "blocked":
                            overall_status = "warning"
                        issues.append({
                            "day": dow,
                            "level": "warning",
                            "message": f"{d_name}: Lead shorter than pull-down time ({calculated_lead_min} min): room may be warm at start."
                        })

        return {
            "status": overall_status,
            "issues": issues,
            "can_apply": overall_status != "blocked"
        }

    async def get_room_recommendation(
        self,
        room_id: str,
        db: AsyncSession,
        unit_scope: str = "both"  # "both" | "unit_1" | "unit_2"
    ) -> Dict[str, Any]:
        """
        GET /api/optimizer/room/{room_id}/recommendation
        Returns full weekly timetable, recommended runs, current timer,
        savings calculations, and all assumptions.
        """
        room = await db.get(RoomModel, room_id)
        if not room:
            # Fallback room query by name or clean fallback
            res = await db.execute(select(RoomModel).where(RoomModel.id == room_id))
            room = res.scalars().first()

        if not room:
            raise ValueError(f"Room {room_id} not found")

        units_res = await db.execute(select(ACUnitModel).where(ACUnitModel.room_id == room_id))
        units = list(units_res.scalars().all())

        # If room has no units in db, synthesize default 2 units
        if not units:
            unit_list = [
                {"id": f"ac-{room_id}-1", "name": "Split Unit 1", "rated_kw": 2.5},
                {"id": f"ac-{room_id}-2", "name": "Split Unit 2", "rated_kw": 2.5}
            ]
        else:
            unit_list = [{"id": u.id, "name": u.name, "rated_kw": u.rated_kw} for u in units]

        total_rated_kw = sum(u["rated_kw"] for u in unit_list)

        # Scale by unit scope
        if unit_scope == "unit_1" and len(unit_list) > 0:
            active_rated_kw = unit_list[0]["rated_kw"]
            unit_scale = active_rated_kw / max(0.1, total_rated_kw)
        elif unit_scope == "unit_2" and len(unit_list) > 1:
            active_rated_kw = unit_list[1]["rated_kw"]
            unit_scale = active_rated_kw / max(0.1, total_rated_kw)
        else:
            active_rated_kw = total_rated_kw
            unit_scale = 1.0

        # Protected room check (Server room)
        is_protected = bool(room.is_critical and ("server" in room.id.lower() or "server" in room.name.lower()))

        # Timetable schedules from database
        sched_res = await db.execute(select(ScheduleModel).where(ScheduleModel.room_id == room_id))
        raw_schedules = list(sched_res.scalars().all())

        timetable_by_day: Dict[int, List[Dict[str, Any]]] = {d: [] for d in range(7)}
        for s in raw_schedules:
            timetable_by_day[s.day_of_week].append({
                "id": s.id,
                "title": s.activity_name or "Session",
                "start_time": s.start_time[:5],
                "end_time": s.end_time[:5],
                "headcount": s.expected_headcount or 30
            })

        # Sort daily sessions
        for d in range(7):
            timetable_by_day[d] = sorted(timetable_by_day[d], key=lambda x: self.time_to_minutes(x["start_time"]))

        # Current Timer (real schedule per day: default 07:00-19:00 for campus labs)
        timer_by_day: Dict[int, Dict[str, Any]] = {}
        timer_hours_by_day: Dict[int, float] = {}

        for dow in range(7):
            # Mon-Sat have timer 07:00-19:00; Sun only if timetable exists
            has_activity = len(timetable_by_day[dow]) > 0
            if dow < 6 or has_activity:
                timer_by_day[dow] = {
                    "start_time": "07:00",
                    "end_time": "19:00",
                    "duration_hours": 12.0
                }
                timer_hours_by_day[dow] = 12.0
            else:
                timer_by_day[dow] = {
                    "start_time": "00:00",
                    "end_time": "00:00",
                    "duration_hours": 0.0
                }
                timer_hours_by_day[dow] = 0.0

        # Physical thermal parameters for 1R1C model
        R_param = 3.5  # °C / kW
        C_param = 6.114  # kWh / °C -> tau = 21.4 min
        Q_cool_sens = active_rated_kw * 0.85
        Q_int = 0.5
        Tout = 31.0  # Morning ambient in °C
        T0 = 31.0

        precool_lead_min, precool_warning, Teq = self.calculate_precool_lead(
            T0=T0,
            Tout=Tout,
            Ttarget=room.target_temp_c,
            R=R_param,
            C=C_param,
            Q_int=Q_int,
            Q_cool_sens=Q_cool_sens
        )

        # Build recommended runs per weekday
        recommended_runs_by_day: Dict[int, List[Dict[str, Any]]] = {}
        recommended_hours_by_day: Dict[int, float] = {}

        for dow in range(7):
            runs = self.build_daily_recommended_runs(
                timetable_blocks=timetable_by_day[dow],
                precool_lead_min=precool_lead_min,
                shutoff_grace_min=self.shutoff_grace_min
            )
            recommended_runs_by_day[dow] = runs
            recommended_hours_by_day[dow] = sum(r["duration_hours"] for r in runs)

        # Baseline M1 ON load and Conformal prediction intervals
        # Lab 204 baseline is 4.65 kW [4.22, 5.08] for both units
        base_p_on = 4.65 * unit_scale
        band_low = 4.22 * unit_scale
        band_high = 5.08 * unit_scale

        savings = self.compute_savings(
            timer_hours_per_day=timer_hours_by_day,
            recommended_hours_per_day=recommended_hours_by_day,
            setpoint=room.target_temp_c,
            baseline_setpoint=room.target_temp_c,
            baseline_p_on_kw=base_p_on,
            band_low_kw=band_low,
            band_high_kw=band_high,
            tariff=self.default_tariff
        )

        # Validate recommended schedule
        validation = self.validate_schedule_bars(
            room=room,
            timetable_by_day=timetable_by_day,
            bars_by_day=recommended_runs_by_day,
            setpoint=room.target_temp_c,
            calculated_lead_min=precool_lead_min
        )

        # Subtitle generator text
        # e.g. "Lab sessions run Monday to Saturday. Two split units."
        active_days = [d for d in range(7) if len(timetable_by_day[d]) > 0]
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if active_days:
            min_d = day_names[min(active_days)]
            max_d = day_names[max(active_days)]
            days_str = f"{min_d} to {max_d}" if min_d != max_d else min_d
        else:
            days_str = "Monday to Friday"

        # Unique activity names
        all_activities = set()
        for d in active_days:
            for s in timetable_by_day[d]:
                all_activities.add(s["title"])
        if any("lab" in a.lower() for a in all_activities):
            act_title = "Lab sessions"
        elif any("lecture" in a.lower() for a in all_activities):
            act_title = "Lectures"
        elif all_activities:
            primary_act = list(all_activities)[0]
            act_title = primary_act if primary_act.endswith("s") else f"{primary_act}s"
        else:
            act_title = "Classes"

        num_units = len(unit_list)
        if num_units == 2:
            units_text = "Two split units."
        elif num_units == 1:
            units_text = "One unit."
        else:
            units_text = f"{num_units} split units."

        generated_subtitle = f"{act_title} run {days_str}. {units_text}"

        # Recommendation Tile texts (most common & exceptions)
        starts = []
        shutoffs = []
        for d in active_days:
            for r in recommended_runs_by_day[d]:
                starts.append((d, r["start_time"]))
                shutoffs.append((d, r["end_time"]))

        # Most common start
        start_counts: Dict[str, int] = {}
        for _, st in starts:
            start_counts[st] = start_counts.get(st, 0) + 1
        common_start = max(start_counts, key=start_counts.get) if start_counts else "08:40"

        # Most common shutoff
        shutoff_counts: Dict[str, int] = {}
        for _, et in shutoffs:
            shutoff_counts[et] = shutoff_counts.get(et, 0) + 1
        common_shutoff = max(shutoff_counts, key=shutoff_counts.get) if shutoff_counts else "13:10"

        # Sub text for exceptions grouped by time
        short_day_names = ["Mon", "Tue", "Thu", "Wed", "Thu", "Fri", "Sat", "Sun"]
        short_day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        time_to_days: Dict[str, List[str]] = {}
        for d, et in shutoffs:
            if et != common_shutoff:
                time_to_days.setdefault(et, []).append(short_day_names[d])

        dedup_exc = []
        for et, day_list in time_to_days.items():
            # Deduplicate days
            unique_days = []
            for day in day_list:
                if day not in unique_days:
                    unique_days.append(day)
            days_label = ", ".join(unique_days)
            dedup_exc.append(f"{days_label} {et}")

        shutoff_subtext = ", ".join(dedup_exc) if dedup_exc else "Consistent shut-off across all days"

        precool_subtext = f"Mon to Fri, {precool_lead_min} min before class"

        return {
            "room_id": room.id,
            "room_name": room.name,
            "room_type": room.room_type,
            "is_critical": room.is_critical,
            "is_protected": is_protected,
            "protected_tooltip": "Protected: never switched off" if is_protected else None,
            "subtitle": generated_subtitle,
            "setpoint_c": room.target_temp_c,
            "min_temp_c": room.min_temp_c,
            "max_temp_c": room.max_temp_c,
            "unit_scope": unit_scope,
            "units": unit_list,
            "has_sunday": len(timetable_by_day[6]) > 0,
            "timetable_by_day": timetable_by_day,
            "timer_by_day": timer_by_day,
            "recommended_runs_by_day": recommended_runs_by_day,
            "recommendation_tile": {
                "precool_start": common_start,
                "precool_subtext": precool_subtext,
                "shutoff": common_shutoff,
                "shutoff_subtext": shutoff_subtext,
                "setpoint": room.target_temp_c,
                "current_timer_label": "07:00–19:00"
            },
            "savings": savings,
            "validation": validation,
            "assumptions": {
                "tariff": self.default_tariff,
                "tariff_unit": "₹/kWh",
                "tariff_source": "Campus Utility Contract Rate (Tariff Settings)",
                "R": R_param,
                "R_unit": "K/kW",
                "C": C_param,
                "C_unit": "kWh/K",
                "tau_minutes": 21.4,
                "pull_down_model": "1R1C Lumped Thermal Mass",
                "pull_down_source": "Building fabric UA & air volume physics",
                "rated_kw": active_rated_kw,
                "rated_kw_source": f"Nameplate: {len(unit_list)} split units ({unit_scope})",
                "baseline_p_on_kw": base_p_on,
                "band_low_kw": band_low,
                "band_high_kw": band_high,
                "baseline_source": "M1 LightGBM baseline model with split-conformal prediction interval",
                "min_lead_min": self.min_lead_min,
                "max_lead_min": self.max_lead_min,
                "shutoff_grace_min": self.shutoff_grace_min,
                "min_off_gap_min": self.min_off_gap_min,
                "elasticity_pct_per_deg": self.elasticity_k * 100.0,
                "elasticity_source": "ASHRAE 55 Heuristic (4.0% per 1.0°C relaxation)",
                "weeks_per_month": self.weeks_per_month,
                "note": "Estimate, synthetic data"
            }
        }

    async def preview_schedule_edit(
        self,
        room_id: str,
        bars_by_day: Dict[int, List[Dict[str, Any]]],
        setpoint: float,
        unit_scope: str = "both",
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        POST /api/optimizer/room/{room_id}/preview
        Computes live validation and savings recalculation during dragging / setpoint changes.
        """
        room = await db.get(RoomModel, room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        units_res = await db.execute(select(ACUnitModel).where(ACUnitModel.room_id == room_id))
        units = list(units_res.scalars().all())
        total_kw = sum(u.rated_kw for u in units) if units else 5.0

        if unit_scope == "unit_1" and len(units) > 0:
            scale = units[0].rated_kw / total_kw
        elif unit_scope == "unit_2" and len(units) > 1:
            scale = units[1].rated_kw / total_kw
        else:
            scale = 1.0

        base_p_on = 4.65 * scale
        band_low = 4.22 * scale
        band_high = 5.08 * scale

        # Calculate recommended hours by day from edited bars
        recommended_hours_by_day = {}
        for dow in range(7):
            bars = bars_by_day.get(dow, [])
            day_hrs = 0.0
            for b in bars:
                st = self.time_to_minutes(b["start_time"])
                et = self.time_to_minutes(b["end_time"])
                day_hrs += max(0.0, (et - st) / 60.0)
            recommended_hours_by_day[dow] = round(day_hrs, 2)

        # Standard timer hours by day (07:00-19:00 = 12h for Mon-Sat)
        timer_hours_by_day = {d: 12.0 for d in range(6)}
        timer_hours_by_day[6] = 0.0

        # Fetch timetable blocks for comfort validation
        sched_res = await db.execute(select(ScheduleModel).where(ScheduleModel.room_id == room_id))
        raw_schedules = list(sched_res.scalars().all())
        timetable_by_day = {d: [] for d in range(7)}
        for s in raw_schedules:
            timetable_by_day[s.day_of_week].append({
                "title": s.activity_name or "Session",
                "start_time": s.start_time[:5],
                "end_time": s.end_time[:5]
            })

        # Calculate precool lead
        precool_lead_min, _, _ = self.calculate_precool_lead(
            T0=31.0, Tout=31.0, Ttarget=setpoint,
            R=3.5, C=6.114, Q_int=0.5, Q_cool_sens=total_kw * scale * 0.85
        )

        validation = self.validate_schedule_bars(
            room=room,
            timetable_by_day=timetable_by_day,
            bars_by_day=bars_by_day,
            setpoint=setpoint,
            calculated_lead_min=precool_lead_min
        )

        savings = self.compute_savings(
            timer_hours_per_day=timer_hours_by_day,
            recommended_hours_per_day=recommended_hours_by_day,
            setpoint=setpoint,
            baseline_setpoint=24.0,
            baseline_p_on_kw=base_p_on,
            band_low_kw=band_low,
            band_high_kw=band_high,
            tariff=self.default_tariff
        )

        return {
            "validation": validation,
            "savings": savings,
            "setpoint": setpoint,
            "precool_lead_min": precool_lead_min
        }


optimizer_service = ScheduleOptimizerService()
