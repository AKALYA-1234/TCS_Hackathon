"""
Data loading and time-based train/cal/test split module for ML pipeline.
Enforces strict time splitting (no shuffle, no leakage) and records dataset SHA256 hashes.
"""
import hashlib
import os

import numpy as np
import pandas as pd

FORBIDDEN_COLUMNS = [
    "anomaly_type",
    "wasted_energy_kwh",
    "wasted_power_kw",
    "wasted_cost_inr",
    "is_anomaly",
    "is_legitimate_decoy",
    "severity",
    "counterfactual_power_kw"
]


def compute_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class DataLoader:
    def __init__(self, data_dir: str = "synthetic_data/output", ashrae_dir: str = "dataset_processed"):
        self.data_dir = data_dir
        self.ashrae_dir = ashrae_dir
        self.manifest_hashes: dict[str, str] = {}
        self._record_hashes()

    def _record_hashes(self) -> None:
        target_files = [
            os.path.join(self.data_dir, "ac_telemetry.parquet"),
            os.path.join(self.data_dir, "weather.parquet"),
            os.path.join(self.data_dir, "occupancy_readings.parquet"),
            os.path.join(self.data_dir, "ground_truth_labels.parquet"),
            os.path.join(self.data_dir, "rooms.parquet"),
            os.path.join(self.data_dir, "schedules.parquet"),
            os.path.join(self.ashrae_dir, "ashrae_chilled_selected.parquet"),
        ]
        for tf in target_files:
            if os.path.exists(tf):
                fname = os.path.basename(tf)
                self.manifest_hashes[fname] = compute_file_sha256(tf)

    def load_telemetry_with_weather(
        self,
        slice_days: int | None = None,
        resolution_mins: int = 15
    ) -> pd.DataFrame:
        """
        Loads ac_telemetry and joins weather, room metadata, and expected timetable schedule.
        Downcasts dtypes for memory safety (float32, category).
        Aggregation resolution: default 15 minutes (ASSUMPTION for thin-laptop CPU efficiency).
        """
        telem_path = os.path.join(self.data_dir, "ac_telemetry.parquet")
        weather_path = os.path.join(self.data_dir, "weather.parquet")
        rooms_path = os.path.join(self.data_dir, "rooms.parquet")
        sched_path = os.path.join(self.data_dir, "schedules.parquet")

        df_t = pd.read_parquet(telem_path)
        df_w = pd.read_parquet(weather_path)
        df_r = pd.read_parquet(rooms_path)
        df_s = pd.read_parquet(sched_path)

        df_t["dt"] = pd.to_datetime(df_t["date_time"])
        df_w["dt"] = pd.to_datetime(df_w["timestamp"])

        if slice_days is not None:
            min_dt = df_t["dt"].min()
            max_dt = min_dt + pd.Timedelta(days=slice_days)
            df_t = df_t[df_t["dt"] < max_dt].copy()
            df_w = df_w[df_w["dt"] < max_dt].copy()

        # Join rooms metadata
        df_t = df_t.merge(
            df_r[["id", "room_type", "area_sqm", "capacity", "design_load_w", "rated_sensible_cooling_w", "target_temp_c"]],
            left_on="room",
            right_on="id",
            how="left"
        ).drop(columns=["id"])

        # Aggregate to target resolution (e.g. 15-min) to save CPU & RAM
        # Round dt to resolution
        df_t["dt_agg"] = df_t["dt"].dt.floor(f"{resolution_mins}min")
        agg_map = {
            "power_kw": "mean",
            "set_temp_c": "mean",
            "room_temp_c": "mean",
            "occupancy": "mean",  # actual detected headcount
            "scheduled_hours": "max",
            "area_sqm": "first",
            "capacity": "first",
            "design_load_w": "first",
            "rated_sensible_cooling_w": "first",
            "target_temp_c": "first",
            "room_type": "first",
            "on_off_status": lambda x: (x == "ON").mean()
        }
        df_agg = df_t.groupby(["room", "ac_unit_id", "dt_agg"], as_index=False).agg(agg_map)
        df_agg.rename(columns={"dt_agg": "dt", "on_off_status": "runtime_fraction"}, inplace=True)

        # Merge weather at dt
        df_w["dt_agg"] = df_w["dt"].dt.floor(f"{resolution_mins}min")
        w_agg = df_w.groupby("dt_agg", as_index=False).agg({
            "outdoor_temp_c": "mean",
            "relative_humidity": "mean"
        }).rename(columns={"dt_agg": "dt"})

        df_merged = df_agg.merge(w_agg, on="dt", how="left")

        # Map schedule expected headcount
        # schedules: room_id, day_of_week, start_time, end_time, expected_headcount
        df_merged["dow"] = df_merged["dt"].dt.dayofweek
        df_merged["minute_of_day"] = df_merged["dt"].dt.hour * 60 + df_merged["dt"].dt.minute

        # Compute timetable expected headcount by matching timetable intervals
        sched_lookup = {}
        for _, s in df_s.iterrows():
            parts_s = s["start_time"].split(":")
            parts_e = s["end_time"].split(":")
            s_min = int(parts_s[0]) * 60 + int(parts_s[1])
            e_min = int(parts_e[0]) * 60 + int(parts_e[1])
            key = (s["room_id"], int(s["day_of_week"]))
            sched_lookup.setdefault(key, []).append((s_min, e_min, int(s["expected_headcount"])))

        def get_expected_hc(row):
            key = (row["room"], row["dow"])
            if key not in sched_lookup:
                return 0
            m = row["minute_of_day"]
            for s_min, e_min, exp_hc in sched_lookup[key]:
                if s_min <= m < e_min:
                    return exp_hc
            return 0

        df_merged["expected_headcount"] = df_merged.apply(get_expected_hc, axis=1)

        # Optimize types
        df_merged["room_type"] = df_merged["room_type"].astype("category")
        df_merged["ac_unit_id"] = df_merged["ac_unit_id"].astype("category")
        df_merged["room"] = df_merged["room"].astype("category")
        
        float_cols = [c for c in df_merged.columns if df_merged[c].dtype == "float64"]
        for c in float_cols:
            df_merged[c] = df_merged[c].astype(np.float32)

        return df_merged.sort_values(["dt", "ac_unit_id"]).reset_index(drop=True)

    def load_ground_truth_labels(self) -> pd.DataFrame:
        gt_path = os.path.join(self.data_dir, "ground_truth_labels.parquet")
        df_gt = pd.read_parquet(gt_path)
        df_gt["start_time"] = pd.to_datetime(df_gt["start_time"])
        df_gt["end_time"] = pd.to_datetime(df_gt["end_time"])
        return df_gt

    def load_ashrae_dataset(self) -> pd.DataFrame:
        ashrae_path = os.path.join(self.ashrae_dir, "ashrae_chilled_selected.parquet")
        df = pd.read_parquet(ashrae_path)
        df["dt"] = pd.to_datetime(df["timestamp"])
        return df.sort_values(["building_id", "dt"]).reset_index(drop=True)

    def time_split(
        self,
        df: pd.DataFrame,
        train_pct: float = 0.70,
        cal_pct: float = 0.15
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Splits dataset strictly by chronological timestamp:
        Train: first 70%
        Calibration: next 15%
        Test: final 15%
        """
        all_dts = np.sort(df["dt"].unique())
        n_dts = len(all_dts)
        train_idx = int(n_dts * train_pct)
        cal_idx = int(n_dts * (train_pct + cal_pct))

        train_cutoff = all_dts[train_idx]
        cal_cutoff = all_dts[cal_idx]

        df_train = df[df["dt"] < train_cutoff].copy()
        df_cal = df[(df["dt"] >= train_cutoff) & (df["dt"] < cal_cutoff)].copy()
        df_test = df[df["dt"] >= cal_cutoff].copy()

        return df_train, df_cal, df_test
