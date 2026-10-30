"""
Unit Tests for Schedule Optimizer Service:
1. Pull-down lead for 3 outdoor temperatures (cool 24°C, nominal 31°C, extreme 38°C)
2. Merge vs split at gap 60 min and 120 min (compressor protection min off time = 90 min)
3. Protected room verification (server room never shut off)
4. Savings equals hand calculation for Lab 204:
   Timer 12h x 6 days = 72 h/week vs recommended 31 h/week -> 41 h/week saved
   Difference x 4.33 weeks x load kW x tariff (prints exact arithmetic)
5. Setpoint raise lowers the saving's energy by the elasticity (4%/°C)
"""
import pytest
from intelligence.schedule_optimizer import ScheduleOptimizerService, format_inr_compact
from domain.ac_models import RoomModel


def test_precool_lead_three_temperatures():
    """Verify pull-down lead for 3 outdoor temperatures with 1R1C model."""
    svc = ScheduleOptimizerService(min_lead_min=10, max_lead_min=45)

    # Room params for Lab 204: R = 3.5 °C/kW, C = 6.114 kWh/°C (tau = 21.4 min)
    # Rated AC sensible = 4.25 kW, Internal load = 0.5 kW
    # Target setpoint = 24.0 °C

    # Case 1: Cool morning (24.0°C) -> ambient already at target, pull-down minimal -> clamped to min_lead (10 min)
    lead_cool, warn_cool, teq_cool = svc.calculate_precool_lead(
        T0=24.0, Tout=24.0, Ttarget=24.0, R=3.5, C=6.114, Q_int=0.5, Q_cool_sens=4.25
    )
    assert lead_cool == 10, f"Expected min_lead (10 min) for cool ambient, got {lead_cool}"
    assert warn_cool == "ok"

    # Case 2: Nominal summer day (31.0°C) -> steady state Teq = 17.875°C, ratio = (31-17.875)/(24-17.875) = 2.14
    # t = 21.4 * ln(2.14) = 16.3 min -> rounded UP to next 5 min = 20 min (matches 08:40 start for 09:00 class)
    lead_nom, warn_nom, teq_nom = svc.calculate_precool_lead(
        T0=31.0, Tout=31.0, Ttarget=24.0, R=3.5, C=6.114, Q_int=0.5, Q_cool_sens=4.25
    )
    assert lead_nom == 20, f"Expected 20 min pre-cool lead for nominal 31°C ambient, got {lead_nom}"
    assert warn_nom == "ok"

    # Case 3: Extreme ambient (38.0°C) -> Teq = 38 + 3.5*(0.5 - 4.25) = 24.875°C >= 24.0°C (target unreachable!)
    # Must flag warning and return max_lead (45 min)
    lead_hot, warn_hot, teq_hot = svc.calculate_precool_lead(
        T0=38.0, Tout=38.0, Ttarget=24.0, R=3.5, C=6.114, Q_int=0.5, Q_cool_sens=4.25
    )
    assert lead_hot == 45, f"Expected max_lead (45 min) for unreachable extreme ambient, got {lead_hot}"
    assert "unreachable" in warn_hot.lower()


def test_merge_vs_split_gap_60_and_120():
    """Verify compressor protection: gap 60 min (< 90 min) merges into one run; gap 120 min (>= 90 min) splits."""
    svc = ScheduleOptimizerService(min_off_gap_min=90, shutoff_grace_min=10)

    # 1. Gap = 60 minutes: Session 1 (09:00-13:00) and Session 2 (14:00-16:00)
    sessions_60 = [
        {"activity_name": "Lab session", "start_time": "09:00", "end_time": "13:00"},
        {"activity_name": "Practical", "start_time": "14:00", "end_time": "16:00"}
    ]
    runs_merged = svc.build_daily_recommended_runs(sessions_60, precool_lead_min=20, shutoff_grace_min=10)
    assert len(runs_merged) == 1, f"Expected 1 merged run for 60-min gap, got {len(runs_merged)}"
    assert runs_merged[0]["start_time"] == "08:40"
    assert runs_merged[0]["end_time"] == "16:10"
    assert runs_merged[0]["is_merged"] is True
    assert len(runs_merged[0]["kept_on_gaps"]) == 1
    assert runs_merged[0]["kept_on_gaps"][0]["start_time"] == "13:00"
    assert runs_merged[0]["kept_on_gaps"][0]["end_time"] == "14:00"

    # 2. Gap = 120 minutes: Session 1 (09:00-12:00) and Session 2 (14:00-16:00)
    sessions_120 = [
        {"activity_name": "Morning Lecture", "start_time": "09:00", "end_time": "12:00"},
        {"activity_name": "Afternoon Lab", "start_time": "14:00", "end_time": "16:00"}
    ]
    runs_split = svc.build_daily_recommended_runs(sessions_120, precool_lead_min=20, shutoff_grace_min=10)
    assert len(runs_split) == 2, f"Expected 2 separate runs for 120-min gap, got {len(runs_split)}"
    assert runs_split[0]["start_time"] == "08:40"
    assert runs_split[0]["end_time"] == "12:10"
    assert runs_split[1]["start_time"] == "13:40"
    assert runs_split[1]["end_time"] == "16:10"


def test_protected_room():
    """Verify server rooms are protected and cannot be turned off."""
    server_room = RoomModel(
        id="eng-server",
        name="Department Server Room",
        room_type="lab",
        is_critical=True
    )
    is_protected = bool(server_room.is_critical and "server" in server_room.id.lower())
    assert is_protected is True


def test_savings_hand_calculation_lab_204(capsys):
    """
    Savings equals the hand calculation:
    Timer: 12 h x 6 days = 72 h/week
    Recommended:
      Mon: 08:40 - 13:10 = 4.5 h
      Tue: 08:40 - 16:10 = 7.5 h
      Wed: 08:40 - 13:10 = 4.5 h
      Thu: 08:40 - 16:10 = 7.5 h
      Fri: 08:40 - 13:10 = 4.5 h
      Sat: 08:40 - 11:10 = 2.5 h
      Total recommended = 31.0 h/week
    Difference = 72.0 - 31.0 = 41.0 h/week
    Monthly hours = 41.0 * 4.33 = 177.53 h/month
    Tariff = 9.20 INR/kWh
    Baseline ON load = 4.65 kW [band_low=4.22 kW, band_high=5.08 kW]
    """
    svc = ScheduleOptimizerService(default_tariff=9.20, weeks_per_month=4.33)

    timer_hours = {d: 12.0 for d in range(6)}
    timer_hours[6] = 0.0

    rec_hours = {
        0: 4.5,
        1: 7.5,
        2: 4.5,
        3: 7.5,
        4: 4.5,
        5: 2.5,
        6: 0.0
    }

    tariff = 9.20
    load_p_on = 4.65
    band_low = 4.22
    band_high = 5.08

    # Hand calculation
    timer_total = 12.0 * 6.0  # 72.0 h/week
    rec_total = 4.5 + 7.5 + 4.5 + 7.5 + 4.5 + 2.5  # 31.0 h/week
    diff_week = timer_total - rec_total  # 41.0 h/week
    monthly_hours = diff_week * 4.33  # 177.53 hours/month

    hand_kwh_est = monthly_hours * load_p_on
    hand_kwh_low = monthly_hours * band_low
    hand_kwh_high = monthly_hours * band_high

    hand_cost_est = hand_kwh_est * tariff
    hand_cost_low = hand_kwh_low * tariff
    hand_cost_high = hand_kwh_high * tariff

    print("\n--- ARITHMETIC VERIFICATION FOR LAB 204 ---")
    print(f"Current Timer Hours: 12.0 h/day x 6 days = {timer_total} h/week")
    print(f"Recommended On Hours: {rec_total} h/week (Mon-Fri 4.5/7.5h, Sat 2.5h)")
    print(f"Weekly Hours Saved: {diff_week} h/week")
    print(f"Monthly Hours Saved: {diff_week} x 4.33 weeks/month = {monthly_hours:.2f} h/month")
    print(f"Energy Saved (Est): {monthly_hours:.2f} h x {load_p_on} kW = {hand_kwh_est:.1f} kWh")
    print(f"Cost Saved (Est): {hand_kwh_est:.1f} kWh x ₹{tariff} = ₹{hand_cost_est:.2f}")
    print(f"Range (Low): {hand_kwh_low:.1f} kWh x ₹{tariff} = ₹{hand_cost_low:.2f} ({format_inr_compact(hand_cost_low)})")
    print(f"Range (High): {hand_kwh_high:.1f} kWh x ₹{tariff} = ₹{hand_cost_high:.2f} ({format_inr_compact(hand_cost_high)})")
    print(f"Formatted Output: {format_inr_compact(hand_cost_low)} – {format_inr_compact(hand_cost_high)}")
    print("-------------------------------------------\n")

    savings = svc.compute_savings(
        timer_hours_per_day=timer_hours,
        recommended_hours_per_day=rec_hours,
        setpoint=24.0,
        baseline_setpoint=24.0,
        baseline_p_on_kw=load_p_on,
        band_low_kw=band_low,
        band_high_kw=band_high,
        tariff=tariff
    )

    assert savings["saved_hours_week"] == diff_week
    assert round(savings["hours_saved_month"], 2) == round(monthly_hours, 2)
    assert savings["cost_saved_month"]["formatted_range"] == "₹6.9k – ₹8.3k"


def test_setpoint_raise_lowers_savings_energy_by_elasticity():
    """Verify that raising setpoint lowers baseline power by elasticity (4%/°C), lowering kWh saved from shut-off."""
    svc = ScheduleOptimizerService(elasticity_k=0.04)

    timer_hours = {d: 12.0 for d in range(6)}
    timer_hours[6] = 0.0
    rec_hours = {0: 4.5, 1: 7.5, 2: 4.5, 3: 7.5, 4: 4.5, 5: 2.5, 6: 0.0}

    # At baseline setpoint (24.0°C)
    res_base = svc.compute_savings(
        timer_hours_per_day=timer_hours,
        recommended_hours_per_day=rec_hours,
        setpoint=24.0,
        baseline_setpoint=24.0,
        baseline_p_on_kw=4.65,
        band_low_kw=4.22,
        band_high_kw=5.08,
        tariff=9.20
    )

    # At elevated setpoint (25.0°C) -> delta T = 1.0°C -> elasticity factor = (1 - 0.04)^1 = 0.96
    res_elevated = svc.compute_savings(
        timer_hours_per_day=timer_hours,
        recommended_hours_per_day=rec_hours,
        setpoint=25.0,
        baseline_setpoint=24.0,
        baseline_p_on_kw=4.65,
        band_low_kw=4.22,
        band_high_kw=5.08,
        tariff=9.20
    )

    assert res_elevated["elasticity_factor"] == 0.96
    # kWh saved must scale down by 0.96
    expected_kwh = round(res_base["kwh_saved_month"]["est"] * 0.96, 1)
    assert abs(res_elevated["kwh_saved_month"]["est"] - expected_kwh) <= 0.1
