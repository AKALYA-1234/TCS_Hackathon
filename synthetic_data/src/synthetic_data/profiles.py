"""
Profiles loader: Loads real ASHRAE chilled-water data and aligned weather,
computes normalized thermal intensity (kW_th / m2), and maps dates cyclically.
Includes a fully self-contained pure-synthetic fallback if the parquet is missing.
"""
import logging
import math
import os
from datetime import datetime

import pandas as pd

logger = logging.getLogger("synthetic_data.profiles")


class AshraeProfileAnchor:
    """
    Manages empirical chilled-water profiles (meter 1) and outdoor weather.
    Anchors synthetic data generation to real building thermal responses.
    """
    def __init__(
        self,
        parquet_path: str,
        fallback_if_missing: bool = True,
        timezone_offset_hours: int = -8
    ):
        self.using_fallback = False
        self.timezone_offset_hours = timezone_offset_hours
        if not os.path.exists(parquet_path):
            if fallback_if_missing:
                logger.warning(f"ASHRAE parquet extract not found at {parquet_path}. Using pure-synthetic physics fallback.")
                self.using_fallback = True
                return
            else:
                raise FileNotFoundError(f"ASHRAE parquet extract not found at: {parquet_path}")

        logger.info(f"Loading empirical ASHRAE profiles from: {parquet_path} (tz offset: {timezone_offset_hours}h)")
        self.df = pd.read_parquet(parquet_path)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])

        # Compute thermal intensity in kW_th / m2
        self.df['intensity_kw_per_sqm'] = self.df['chilled_water_reading_kwh'] / self.df['square_meters']

        self.df['doy'] = self.df['timestamp'].dt.dayofyear
        self.df['dow'] = self.df['timestamp'].dt.dayofweek
        self.df['hour'] = self.df['timestamp'].dt.hour
        self.df['month'] = self.df['timestamp'].dt.month

        # Group pre-indexed cache
        self._lookup: dict[tuple[int, int, int], dict[str, float]] = {}
        for row in self.df.itertuples():
            b_id = int(getattr(row, "building_id"))  # noqa: B009
            doy = int(getattr(row, "doy"))  # noqa: B009
            hr = int(getattr(row, "hour"))  # noqa: B009
            key = (b_id, doy, hr)
            air_t = float(getattr(row, "air_temperature_filled"))  # noqa: B009
            dew_t = float(getattr(row, "dew_temperature_filled"))  # noqa: B009
            w_spd = getattr(row, "wind_speed")  # noqa: B009
            self._lookup[key] = {
                "intensity_kw_per_sqm": float(getattr(row, "intensity_kw_per_sqm")),  # noqa: B009
                "outdoor_temp_c": air_t,
                "dew_temp_c": dew_t,
                "relative_humidity": float(self._calc_rh(air_t, dew_t)),
                "wind_speed": float(w_spd) if not pd.isna(w_spd) else 2.5,
                "is_anomaly": bool(getattr(row, "is_anomaly"))  # noqa: B009
            }

    @staticmethod
    def _calc_rh(t_c: float, dp_c: float) -> float:
        # Magnus-Tetens approximation for relative humidity from dew point
        try:
            a, b = 17.27, 237.7
            alpha_t = (a * t_c) / (b + t_c)
            alpha_dp = (a * dp_c) / (b + dp_c)
            rh = 100.0 * math.exp(alpha_dp - alpha_t)
            return max(10.0, min(95.0, rh))
        except (ValueError, ZeroDivisionError):
            return 45.0

    def get_profile_point(self, archetype_building_id: int, sim_dt: datetime) -> dict[str, float]:
        """
        Retrieves normalized intensity and outdoor temperature for a simulated datetime.
        Uses cyclic day-of-year + day-of-week matching to preserve seasonal & diurnal shape.
        """
        if self.using_fallback:
            return self._synthetic_point(archetype_building_id, sim_dt)

        sim_doy = sim_dt.timetuple().tm_yday
        sim_hour = sim_dt.hour

        # Try exact DOY first
        key = (archetype_building_id, sim_doy, sim_hour)
        if key in self._lookup:
            return self._lookup[key]

        # Search nearby days within +/- 7 days
        for offset in [0, -7, 7, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6]:
            target_doy = max(1, min(365, sim_doy + offset))
            candidate_key = (archetype_building_id, target_doy, sim_hour)
            if candidate_key in self._lookup:
                return self._lookup[candidate_key]

        # Fallback to mean values for that hour across building
        subset = self.df[(self.df['building_id'] == archetype_building_id) & (self.df['hour'] == sim_hour)]
        if len(subset) > 0:
            avg_temp = float(subset['air_temperature_filled'].mean())  # pyright: ignore[reportArgumentType]
            avg_dew = float(subset['dew_temperature_filled'].mean())    # pyright: ignore[reportArgumentType]
            intensity_val = float(subset['intensity_kw_per_sqm'].mean()) # pyright: ignore[reportArgumentType]
            return {
                "intensity_kw_per_sqm": intensity_val,
                "outdoor_temp_c": avg_temp,
                "dew_temp_c": avg_dew,
                "relative_humidity": self._calc_rh(avg_temp, avg_dew),
                "wind_speed": 2.5,
                "is_anomaly": False
            }

        return self._synthetic_point(archetype_building_id, sim_dt)

    def _synthetic_point(self, archetype_building_id: int, sim_dt: datetime) -> dict[str, float]:
        """
        Pure-synthetic fallback: generates physical diurnal temperatures (peak 15:00, min 05:00)
        and thermal load intensity if parquet extract is unavailable.
        """
        hour = sim_dt.hour + sim_dt.minute / 60.0
        doy = sim_dt.timetuple().tm_yday
        # Summer peak in Phoenix / warm climate
        seasonal = 28.0 + 8.0 * math.sin((doy - 80) * 2 * math.pi / 365)
        diurnal = 6.0 * math.sin((hour - 9) * 2 * math.pi / 24)
        t_out = round(seasonal + diurnal, 1)
        dew_point = round(max(0.0, t_out - 18.0), 1)
        rh = self._calc_rh(t_out, dew_point)

        # Baseline intensity ~ 0.025 to 0.055 kW/m2
        intensity = 0.022 + 0.001 * max(0.0, t_out - 22.0)
        return {
            "intensity_kw_per_sqm": float(intensity),
            "outdoor_temp_c": float(t_out),
            "dew_temp_c": float(dew_point),
            "relative_humidity": float(rh),
            "wind_speed": 2.5,
            "is_anomaly": False
        }
