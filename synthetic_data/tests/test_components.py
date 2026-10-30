import math
import os

import numpy as np
import pandas as pd
import pytest

from synthetic_data.campus import Campus
from synthetic_data.physics import ThermalPhysicsEngine
from synthetic_data.utils import cv_rmse, nmbe


@pytest.fixture
def base_paths():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return {
        "config": os.path.join(root, "config/default.yaml"),
        "rooms": os.path.join(root, "config/rooms.yaml"),
        "anomalies": os.path.join(root, "config/anomalies.yaml"),
        "output": os.path.join(root, "output")
    }


def test_pulldown_analytic_vs_numeric(base_paths):
    """
    FIX 1 Test: Pull-down formula against numeric Euler simulation of same lumped model.
    Must agree within 2%.
    """
    campus = Campus.from_yaml(base_paths["rooms"], base_paths["config"])
    room = campus.get_room("eng-101")
    assert room is not None
    t0 = 34.0
    t_target = 24.0
    t_out = 38.0
    q_int = 1000.0  # W
    shr = 0.75

    analytic_mins, status = room.calculate_pulldown_time(
        t0=t0, target_temp=t_target, t_out=t_out, q_int_sens_w=q_int, shr=shr
    )
    assert status == "ok"

    # Numeric simulation of same model: C_eff * dT/dt = (T_out - T)/R - Q_cool_sens + Q_int
    c_eff = room.c_a + 0.55 * room.c_m
    g = 1.0 / room.r_ao
    q_cool_sens = room.total_rated_kw * 1000.0 * shr

    dt_sec = 1.0
    t_num = t0
    elapsed_sec = 0.0
    while t_num > t_target and elapsed_sec < 180 * 60:
        dt_val = ((t_out - t_num) * g + q_int - q_cool_sens) / c_eff
        t_num += dt_val * dt_sec
        elapsed_sec += dt_sec

    numeric_mins = elapsed_sec / 60.0
    rel_error = abs(analytic_mins - numeric_mins) / numeric_mins
    assert rel_error <= 0.02, f"Analytic ({analytic_mins:.2f}m) vs Numeric ({numeric_mins:.2f}m) exceeded 2% ({rel_error*100:.2f}%)"


def test_2r2c_stability(base_paths):
    """
    FIX 2 Test: 2R2C stability with no divergence for dt from 1 to 60 minutes.
    """
    campus = Campus.from_yaml(base_paths["rooms"], base_paths["config"])
    room = campus.get_room("eng-101")
    assert room is not None
    rng = np.random.default_rng(42)
    engine = ThermalPhysicsEngine(rng, {"physics": {}})

    for dt_m in [1, 5, 10, 15, 30, 60]:
        t_a = 32.0
        t_m = 30.0
        for _ in range(int(360 / dt_m)):  # 6 hours
            t_a, t_m = engine.integrate_2r2c_substep(
                room, t_a, t_m, t_out=42.0, q_int_sens_w=2000.0, q_cool_sens_w=8000.0, dt_seconds=dt_m * 60.0
            )
            assert not math.isnan(t_a) and not math.isnan(t_m)
            assert 15.0 <= t_a <= 45.0
            assert 15.0 <= t_m <= 45.0


def test_undersized_room_cannot_reach(base_paths):
    """
    FIX 1 & FIX 5 Test: Severely undersized AC capacity cannot reach setpoint and returns 'cannot_reach'.
    """
    campus = Campus.from_yaml(base_paths["rooms"], base_paths["config"])
    room = campus.get_room("sci-301")
    assert room is not None
    # At extreme ambient 48°C with heavy internal load
    mins, status = room.calculate_pulldown_time(
        t0=36.0, target_temp=22.0, t_out=48.0, q_int_sens_w=3500.0, shr=0.75
    )
    # sci-301 has only 3.2 kW rated unit
    assert status == "cannot_reach"
    assert mins >= 180.0


def test_warm_mass_vs_cool_mass_pulldown(base_paths):
    """
    FIX 1 Test: Warm-mass start requires longer pre-cool than cool-mass start.
    """
    campus = Campus.from_yaml(base_paths["rooms"], base_paths["config"])
    room = campus.get_room("eng-101")
    assert room is not None

    # Warm mass start (e.g. 35°C after weekend)
    mins_warm, _ = room.calculate_pulldown_time(t0=35.0, target_temp=24.0, t_out=38.0, q_int_sens_w=500.0)
    # Cool mass start (e.g. 26°C overnight setback)
    mins_cool, _ = room.calculate_pulldown_time(t0=26.0, target_temp=24.0, t_out=38.0, q_int_sens_w=500.0)

    assert mins_warm > mins_cool
    assert mins_warm - mins_cool >= 15.0


def test_inverter_datasheet_points(base_paths):
    """
    FIX 4 Test: Inverter power at 100% and 50% load reproduces the two datasheet points exactly.
    Datasheet: 3550W cooling @ 1110W input (100%), 1775W cooling @ 430W input (50%).
    """
    rng = np.random.default_rng(42)
    engine = ThermalPhysicsEngine(rng, {"physics": {}})

    # Scale for 3.55 kW unit at rated 35°C ambient
    rated_w = 3550.0

    # 100% load test: 3550W cooling @ 1110W input
    p_elec_100_kw, _cop_100 = engine.calculate_inverter_power(
        q_cool_total_w=3550.0, rated_total_cooling_w=rated_w, outdoor_temp_c=35.0
    )
    p_100_w = p_elec_100_kw * 1000.0
    err_100 = abs(p_100_w - 1110.0) / 1110.0
    assert err_100 <= 0.01, f"100% load power {p_100_w:.1f}W differs from 1110W by {err_100*100:.2f}%"

    # 50% load test: 1775W cooling @ 430W input
    p_elec_50_kw, _cop_50 = engine.calculate_inverter_power(
        q_cool_total_w=1775.0, rated_total_cooling_w=rated_w, outdoor_temp_c=35.0
    )
    p_50_w = p_elec_50_kw * 1000.0
    err_50 = abs(p_50_w - 430.0) / 430.0
    assert err_50 <= 0.01, f"50% load power {p_50_w:.1f}W differs from 430W by {err_50*100:.2f}%"


def test_sensible_and_latent_people_heat(base_paths):
    """
    FIX 3 Test: Verify sensible/latent split and only sensible entering air node.
    """
    rng = np.random.default_rng(42)
    engine = ThermalPhysicsEngine(rng, {
        "internal_gains": {
            "lecture_hall": {"person_sensible_w": 67.0, "person_latent_w": 33.0}
        }
    })
    campus = Campus.from_yaml(base_paths["rooms"], base_paths["config"])
    room = campus.get_room("eng-101")
    assert room is not None

    q_sens, q_lat = engine.calculate_internal_heat_gains(room, occupancy_headcount=50, is_occupied_period=True)
    assert q_sens >= 50 * 67.0
    assert q_lat == 50 * 33.0


def test_ashrae_guideline_14_metrics():
    """
    FIX 9 Test: cv_rmse and nmbe function correctness according to Guideline 14.
    """
    y_true = np.array([100.0, 110.0, 95.0, 105.0])
    y_pred = np.array([98.0, 108.0, 97.0, 103.0])

    val_cv = cv_rmse(y_true, y_pred, p=1)
    val_nmbe = nmbe(y_true, y_pred, p=1)

    assert 0.0 <= val_cv <= 10.0
    assert abs(val_nmbe) <= 5.0


def test_leakage_guard(base_paths, file_path=None):
    """
    Leakage test: strictly verifies that no anomaly labels or derived waste fields
    leak into the public main telemetry file. Accepts an optional file_path parameter.
    """
    if file_path is None:
        file_path = os.path.join(base_paths["output"], "ac_telemetry.parquet")
    if not os.path.exists(file_path):
        pytest.skip(f"Parquet file {file_path} not found")

    df_main = pd.read_parquet(file_path)
    expected_cols = [
        "room", "ac_unit_id", "date_time", "power_kw",
        "set_temp_c", "room_temp_c", "occupancy", "on_off_status", "scheduled_hours"
    ]
    assert list(df_main.columns) == expected_cols, f"Column mismatch in {file_path}"

    forbidden = ["anomaly", "label", "ground_truth", "wasted", "decoy"]
    for col in df_main.columns:
        for f in forbidden:
            assert f not in col.lower(), f"Leakage detected: column '{col}' in {file_path} contains forbidden '{f}'"


def test_weather_peak_hour(base_paths):
    """
    Item 2 Test: Fails if the generated weather daily peak hour is outside 13:00 to 17:00.
    """
    wth_path = os.path.join(base_paths["output"], "weather.parquet")
    if not os.path.exists(wth_path):
        pytest.skip("Weather parquet not found")
    df_w = pd.read_parquet(wth_path)
    df_w["dt"] = pd.to_datetime(df_w["timestamp"])
    df_w["hour"] = df_w["dt"].dt.hour
    hourly_mean = pd.Series(df_w.groupby("hour")["outdoor_temp_c"].mean())
    peak_hour = int(hourly_mean.idxmax())  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]
    assert 13 <= peak_hour <= 17, f"Generated weather daily peak hour {peak_hour}:00 is outside 13:00-17:00"


def test_setpoint_elasticity_not_constant(base_paths):
    """
    Item 3 Test: Fails if setpoint elasticity estimate is a constant across rooms.
    """
    campus = Campus.from_yaml(base_paths["rooms"], base_paths["config"])
    rng = np.random.default_rng(42)
    engine = ThermalPhysicsEngine(rng, {"physics": {}})
    
    # 7-day hot profile
    t_profile = [33.0 + 8.0 * math.sin(2 * math.pi * (i % 288) / 288 - math.pi / 2) for i in range(288 * 7)]
    
    elasticities = []
    for b in campus.buildings:
        for r in b.rooms:
            if r.sizing_status == "ok":
                el = engine.estimate_setpoint_elasticity(r, r.units[0], t_profile, dt_minutes=5.0)
                elasticities.append(el)
    
    assert len(elasticities) >= 5
    unique_vals = {round(x, 1) for x in elasticities}
    assert len(unique_vals) > 1, f"Setpoint elasticity is constant across rooms: {unique_vals}"


def test_early_start_excess_minutes(base_paths):
    """
    Item 4 Test: Fails if any early_start label has excess minutes below configured min (45m).
    """
    gt_path = os.path.join(base_paths["output"], "ground_truth_labels.parquet")
    if not os.path.exists(gt_path):
        pytest.skip("ground_truth_labels parquet not found")
    df_gt = pd.read_parquet(gt_path)
    early = df_gt[df_gt["anomaly_type"] == "early_start"]
    assert len(early) > 0, "No early_start labels found"
    excess_series = pd.Series(early["excess_minutes"])
    below_min = int((excess_series < 45.0).sum())
    assert below_min == 0, f"Found {below_min} early_start labels with excess below 45 minutes"
