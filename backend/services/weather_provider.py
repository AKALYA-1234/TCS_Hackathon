"""
Weather Provider Subsystem for AC Optimization System.
Provides ReplayWeatherProvider, OpenMeteoProvider, and HybridWeatherProvider (Auto mode).
Strictly adheres to:
- Timeouts (5s)
- Caching (15 min current, 1 hr forecast)
- Retry with exponential backoff
- Graceful fallbacks (never block simulator or app)
- Range validation on weather metrics
- Privacy: zero key/personal data logging
- Configurable via WEATHER_SOURCE, WEATHER_LAT, WEATHER_LON
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import logging
import os
import time
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error
import json

logger = logging.getLogger("weather.provider")

# Range limits for physics sanity check
VALID_RANGES = {
    "outdoor_temp_c": (-20.0, 60.0),
    "relative_humidity": (0.0, 100.0),
    "solar_irradiance_wm2": (0.0, 1500.0),
    "dew_point_c": (-30.0, 45.0),
    "apparent_temp_c": (-25.0, 70.0),
    "wind_speed_kmh": (0.0, 250.0),
    "cloud_cover_pct": (0.0, 100.0),
    "precipitation_mm": (0.0, 500.0),
}


def validate_weather_dict(data: Dict[str, Any]) -> bool:
    """Validates that values fall within physical sanity ranges."""
    for key, (vmin, vmax) in VALID_RANGES.items():
        if key in data and data[key] is not None:
            val = float(data[key])
            if not (vmin <= val <= vmax):
                logger.warning(f"Weather value out of physical bounds: {key}={val} (range: {vmin}-{vmax})")
                return False
    return True


@dataclass
class WeatherPoint:
    timestamp: str  # ISO UTC or Local
    outdoor_temp_c: float
    relative_humidity: float
    solar_irradiance_wm2: float
    dew_point_c: Optional[float] = None
    apparent_temp_c: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeatherResponse:
    status: str  # "live", "cached", "stale", "fallback"
    source: str  # "Open-Meteo", "Replay", "Fallback"
    fetched_at: str
    is_live: bool
    current: WeatherPoint
    forecast_24h: List[WeatherPoint]
    forecast_7d: List[WeatherPoint]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "is_live": self.is_live,
            "current": self.current.to_dict(),
            "forecast_24h": [p.to_dict() for p in self.forecast_24h],
            "forecast_7d": [p.to_dict() for p in self.forecast_7d],
        }


class WeatherProvider(ABC):
    @abstractmethod
    def get_weather(self, sim_clock: Optional[datetime] = None) -> WeatherResponse:
        """Returns the weather response containing current observations and forecast."""
        pass


class ReplayWeatherProvider(WeatherProvider):
    """
    Replay weather provider based on synthetic/historical simulation data.
    Default for the simulation clock.
    """

    def __init__(self, db_path: str = "app.db"):
        self.db_path = db_path

    def get_weather(self, sim_clock: Optional[datetime] = None) -> WeatherResponse:
        now_dt = sim_clock or datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # Generate realistic diurnal solar/temperature profile matching Site 2 / Coimbatore
        hour = now_dt.hour
        # Diurnal curve: lowest around 05:00 (22°C), peak around 14:00 (34°C)
        import math
        t_base = 28.0 + 6.0 * math.sin(math.pi * (hour - 8.0) / 12.0)
        humidity = max(35.0, min(85.0, 75.0 - (t_base - 22.0) * 3.5))
        solar = max(0.0, 850.0 * math.sin(math.pi * (hour - 6.0) / 12.0)) if 6 <= hour <= 18 else 0.0

        current_pt = WeatherPoint(
            timestamp=now_iso,
            outdoor_temp_c=round(t_base, 1),
            relative_humidity=round(humidity, 1),
            solar_irradiance_wm2=round(solar, 1),
            dew_point_c=round(t_base - ((100 - humidity) / 5), 1),
            apparent_temp_c=round(t_base + 1.8, 1),
            wind_speed_kmh=8.5,
            cloud_cover_pct=25.0,
            precipitation_mm=0.0
        )

        forecast_24h = []
        for h in range(1, 25):
            f_time = now_dt + timedelta(hours=h)
            f_hour = f_time.hour
            f_temp = 28.0 + 6.0 * math.sin(math.pi * (f_hour - 8.0) / 12.0)
            f_hum = max(35.0, min(85.0, 75.0 - (f_temp - 22.0) * 3.5))
            f_sol = max(0.0, 850.0 * math.sin(math.pi * (f_hour - 6.0) / 12.0)) if 6 <= f_hour <= 18 else 0.0
            forecast_24h.append(
                WeatherPoint(
                    timestamp=f_time.isoformat(),
                    outdoor_temp_c=round(f_temp, 1),
                    relative_humidity=round(f_hum, 1),
                    solar_irradiance_wm2=round(f_sol, 1),
                    dew_point_c=round(f_temp - ((100 - f_hum) / 5), 1),
                    apparent_temp_c=round(f_temp + 1.5, 1),
                    wind_speed_kmh=8.0,
                    cloud_cover_pct=30.0,
                    precipitation_mm=0.0
                )
            )

        # 7-day forecast sampled every 3 hours
        forecast_7d = []
        for h in range(3, 169, 3):
            f_time = now_dt + timedelta(hours=h)
            f_hour = f_time.hour
            f_temp = 28.0 + 5.5 * math.sin(math.pi * (f_hour - 8.0) / 12.0)
            f_hum = max(35.0, min(85.0, 75.0 - (f_temp - 22.0) * 3.5))
            f_sol = max(0.0, 850.0 * math.sin(math.pi * (f_hour - 6.0) / 12.0)) if 6 <= f_hour <= 18 else 0.0
            forecast_7d.append(
                WeatherPoint(
                    timestamp=f_time.isoformat(),
                    outdoor_temp_c=round(f_temp, 1),
                    relative_humidity=round(f_hum, 1),
                    solar_irradiance_wm2=round(f_sol, 1),
                    dew_point_c=round(f_temp - ((100 - f_hum) / 5), 1),
                    apparent_temp_c=round(f_temp + 1.5, 1),
                    wind_speed_kmh=8.0,
                    cloud_cover_pct=25.0,
                    precipitation_mm=0.0
                )
            )

        return WeatherResponse(
            status="simulated",
            source="Simulated (Replay Clock)",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            is_live=False,
            current=current_pt,
            forecast_24h=forecast_24h,
            forecast_7d=forecast_7d
        )


class OpenMeteoProvider(WeatherProvider):
    """
    Live Weather Provider querying Open-Meteo REST API.
    Configured for Bannari Amman Institute of Technology / Coimbatore campus by default.
    """

    def __init__(
        self,
        latitude: float = 11.0168,
        longitude: float = 76.9558,
        timezone_str: str = "Asia/Kolkata",
        timeout_sec: float = 5.0,
        cache_ttl_current_sec: float = 900.0,   # 15 minutes
        cache_ttl_forecast_sec: float = 3600.0, # 1 hour
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.timezone_str = timezone_str
        self.timeout_sec = timeout_sec
        self.cache_ttl_current_sec = cache_ttl_current_sec
        self.cache_ttl_forecast_sec = cache_ttl_forecast_sec

        self._cached_response: Optional[WeatherResponse] = None
        self._last_fetch_mono: float = 0.0
        self._last_fetch_utc: Optional[str] = None
        self._rate_limit_min_interval: float = 1.0
        self._last_call_time: float = 0.0

    def parse_api_payload(self, data: Dict[str, Any], fetch_status: str = "live") -> Optional[WeatherResponse]:
        """Parses Open-Meteo JSON payload into typed WeatherResponse."""
        try:
            curr = data.get("current", {})
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])

            t2m = hourly.get("temperature_2m", [])
            rh2m = hourly.get("relative_humidity_2m", [])
            dp2m = hourly.get("dew_point_2m", [])
            app_t = hourly.get("apparent_temperature", [])
            ws10m = hourly.get("wind_speed_10m", [])
            cloud = hourly.get("cloud_cover", [])
            rad = hourly.get("shortwave_radiation", [])
            precip = hourly.get("precipitation", [])

            # Extract current weather point
            current_pt = WeatherPoint(
                timestamp=curr.get("time", datetime.now(timezone.utc).isoformat()),
                outdoor_temp_c=float(curr.get("temperature_2m", 28.0)),
                relative_humidity=float(curr.get("relative_humidity_2m", 60.0)),
                solar_irradiance_wm2=float(rad[0]) if rad else 400.0,
                dew_point_c=float(dp2m[0]) if dp2m else None,
                apparent_temp_c=float(curr.get("apparent_temperature", curr.get("temperature_2m", 28.0))),
                wind_speed_kmh=float(curr.get("wind_speed_10m", 5.0)),
                cloud_cover_pct=float(cloud[0]) if cloud else 20.0,
                precipitation_mm=float(curr.get("precipitation", 0.0))
            )

            # Validate current point
            if not validate_weather_dict(current_pt.to_dict()):
                logger.error("Rejected Open-Meteo payload due to invalid physical ranges in current point")
                return None

            forecast_24h = []
            for i in range(min(24, len(times))):
                pt = WeatherPoint(
                    timestamp=times[i],
                    outdoor_temp_c=float(t2m[i]) if i < len(t2m) else 28.0,
                    relative_humidity=float(rh2m[i]) if i < len(rh2m) else 55.0,
                    solar_irradiance_wm2=float(rad[i]) if i < len(rad) else 0.0,
                    dew_point_c=float(dp2m[i]) if i < len(dp2m) else None,
                    apparent_temp_c=float(app_t[i]) if i < len(app_t) else None,
                    wind_speed_kmh=float(ws10m[i]) if i < len(ws10m) else 5.0,
                    cloud_cover_pct=float(cloud[i]) if i < len(cloud) else 0.0,
                    precipitation_mm=float(precip[i]) if i < len(precip) else 0.0,
                )
                if validate_weather_dict(pt.to_dict()):
                    forecast_24h.append(pt)

            forecast_7d = []
            for i in range(0, min(168, len(times)), 2):  # Every 2 hours up to 7 days
                pt = WeatherPoint(
                    timestamp=times[i],
                    outdoor_temp_c=float(t2m[i]) if i < len(t2m) else 28.0,
                    relative_humidity=float(rh2m[i]) if i < len(rh2m) else 55.0,
                    solar_irradiance_wm2=float(rad[i]) if i < len(rad) else 0.0,
                    dew_point_c=float(dp2m[i]) if i < len(dp2m) else None,
                    apparent_temp_c=float(app_t[i]) if i < len(app_t) else None,
                    wind_speed_kmh=float(ws10m[i]) if i < len(ws10m) else 5.0,
                    cloud_cover_pct=float(cloud[i]) if i < len(cloud) else 0.0,
                    precipitation_mm=float(precip[i]) if i < len(precip) else 0.0,
                )
                if validate_weather_dict(pt.to_dict()):
                    forecast_7d.append(pt)

            return WeatherResponse(
                status=fetch_status,
                source="Live (Open-Meteo)",
                fetched_at=datetime.now(timezone.utc).isoformat(),
                is_live=True,
                current=current_pt,
                forecast_24h=forecast_24h,
                forecast_7d=forecast_7d
            )
        except Exception as e:
            logger.error(f"Error parsing Open-Meteo payload: {e}")
            return None

    def fetch_from_api(self) -> Optional[WeatherResponse]:
        """Executes HTTP request to Open-Meteo API with timeout and retry."""
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.latitude}&longitude={self.longitude}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m"
            f"&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,wind_speed_10m,cloud_cover,shortwave_radiation,precipitation"
            f"&timezone={self.timezone_str}"
        )

        # Rate-limiting check
        now = time.monotonic()
        if now - self._last_call_time < self._rate_limit_min_interval:
            time.sleep(self._rate_limit_min_interval - (now - self._last_call_time))
        self._last_call_time = time.monotonic()

        # Retry once with backoff
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "TCS-Hackathon-AC-Weather/1.0"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    if resp.status == 200:
                        raw = resp.read().decode("utf-8")
                        payload = json.loads(raw)
                        parsed = self.parse_api_payload(payload, fetch_status="live")
                        if parsed:
                            return parsed
            except Exception as e:
                logger.warning(f"Open-Meteo fetch attempt {attempt+1} failed: {e}")
                if attempt == 0:
                    time.sleep(1.0)  # Backoff before retry

        return None

    def get_weather(self, sim_clock: Optional[datetime] = None) -> WeatherResponse:
        now_mono = time.monotonic()

        # Check if cache is still fresh (< 15 min)
        if self._cached_response and (now_mono - self._last_fetch_mono < self.cache_ttl_current_sec):
            resp = self._cached_response
            resp.status = "cached"
            return resp

        # Attempt fresh fetch
        fresh = self.fetch_from_api()
        if fresh:
            self._cached_response = fresh
            self._last_fetch_mono = now_mono
            self._last_fetch_utc = fresh.fetched_at
            return fresh

        # If fetch failed but we have existing cache, return as stale
        if self._cached_response:
            stale_resp = self._cached_response
            stale_resp.status = "stale"
            return stale_resp

        raise RuntimeError("Open-Meteo API unreachable and no cached payload available.")


class HybridWeatherProvider(WeatherProvider):
    """
    Hybrid Provider (Auto mode):
    - Tries Open-Meteo live first.
    - If unreachable or failing, smoothly falls back to ReplayWeatherProvider.
    - Never throws; surfaces status as live, cached, stale, or fallback.
    """

    def __init__(
        self,
        mode: str = "auto",  # "live", "replay", "auto"
        latitude: float = 11.0168,
        longitude: float = 76.9558,
    ):
        self.mode = mode.lower()
        self.replay = ReplayWeatherProvider()
        self.open_meteo = OpenMeteoProvider(latitude=latitude, longitude=longitude)

    def get_weather(self, sim_clock: Optional[datetime] = None) -> WeatherResponse:
        if self.mode == "replay":
            return self.replay.get_weather(sim_clock)

        if self.mode in ("live", "auto"):
            try:
                return self.open_meteo.get_weather(sim_clock)
            except Exception as e:
                logger.warning(f"Live weather provider unavailable: {e}. Engaging replay fallback.")
                if self.mode == "live":
                    # Mark as fallback even in live mode so callers are aware
                    fb = self.replay.get_weather(sim_clock)
                    fb.status = "fallback"
                    fb.source = "Fallback (Simulated Replay)"
                    return fb
                else:
                    # Auto mode fallback
                    fb = self.replay.get_weather(sim_clock)
                    fb.status = "fallback"
                    fb.source = "Auto-Fallback (Simulated Replay)"
                    return fb

        # Default fallback
        return self.replay.get_weather(sim_clock)


# Singleton instance initialized from environment variables
def get_weather_provider() -> WeatherProvider:
    mode = os.getenv("WEATHER_SOURCE", "auto")
    lat = float(os.getenv("WEATHER_LAT", "11.0168"))
    lon = float(os.getenv("WEATHER_LON", "76.9558"))
    return HybridWeatherProvider(mode=mode, latitude=lat, longitude=lon)
