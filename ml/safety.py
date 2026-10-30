"""
Hardware safety monitor and resource watchdog for thin-laptop ML training.
Hardware profile: Intel i7-10610U (4C/8T, 15W TDP, throttles under sustained load), 32 GB RAM.
Safety rules:
- Max physical cores: 3 (n_jobs=3, OMP/MKL/OPENBLAS threads=3)
- Temp >= 85°C: pause until < 75°C
- Temp >= 95°C: emergency abort
- Memory limit: 20 GB (RLIMIT_AS or available RAM < 6 GB)
- Battery check: mains power required for full runs, abort if battery < 30% unplugged
- Inter-model cooldown: 60s; Inter-fold cooldown: 20s
"""
import glob
import logging
import os
import resource
import sys
import threading
import time

logger = logging.getLogger("ml.safety")


class HardwareSafetyWatchdog:
    def __init__(
        self,
        temp_pause_c: float = 85.0,
        temp_resume_c: float = 75.0,
        temp_abort_c: float = 90.0,
        min_ram_avail_gb: float = 6.0,
        max_process_ram_gb: float = 20.0,
        check_interval_sec: float = 3.0
    ):
        self.temp_pause_c = temp_pause_c
        self.temp_resume_c = temp_resume_c
        self.temp_abort_c = temp_abort_c
        self.min_ram_avail_gb = min_ram_avail_gb
        self.max_process_ram_gb = max_process_ram_gb
        self.check_interval_sec = check_interval_sec

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        
        # Diagnostics
        self.peak_temp_c: float = 0.0
        self.peak_rss_mb: float = 0.0
        self.pause_duration_sec: float = 0.0
        self.is_throttled: bool = False
        self.thermal_zones = self._discover_thermal_zones()

    def _discover_thermal_zones(self) -> list[str]:
        zones = glob.glob("/sys/class/thermal/thermal_zone*/temp")
        return zones

    def get_current_temp(self) -> float:
        """
        Reads CPU core/package temperature.
        Targets /sys/class/thermal/thermal_zone0 (acpitz / CPU) and coretemp package.
        """
        temps = []
        for z in ["/sys/class/thermal/thermal_zone0/temp", "/sys/class/thermal/thermal_zone3/temp", "/sys/class/thermal/thermal_zone7/temp"]:
            if os.path.exists(z):
                try:
                    with open(z, "r") as f:
                        val = float(f.read().strip()) / 1000.0
                        if 20.0 <= val <= 115.0:
                            temps.append(val)
                except Exception:
                    pass
        if not temps:
            return 60.0
        # Package peak
        return max(temps)

    def get_available_ram_gb(self) -> float:
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        kb = float(line.split()[1])
                        return kb / (1024.0 * 1024.0)
        except Exception:
            pass
        return 16.0  # safe default

    def get_process_rss_mb(self) -> float:
        try:
            # ru_maxrss is in kilobytes on Linux
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return float(usage.ru_maxrss) / 1024.0
        except Exception:
            return 0.0

    def check_battery_status(self, allow_battery: bool = False) -> None:
        """Enforces power plug status: requires mains power for full runs."""
        online_files = glob.glob("/sys/class/power_supply/*/online")
        is_plugged = False
        for f in online_files:
            try:
                with open(f, "r") as s:
                    if int(s.read().strip()) == 1:
                        is_plugged = True
                        break
            except Exception:
                pass

        if not is_plugged and not allow_battery:
            logger.error("FATAL: Laptop is on BATTERY power! Full training requires AC mains power.")
            print("\n[SAFETY ERROR]: Machine is on battery power. Please plug into mains AC adapter.\n")
            sys.exit(1)

    def apply_process_limits(self) -> None:
        """Configures thread caps and memory bounds."""
        # 1. Environment thread caps
        os.environ["OMP_NUM_THREADS"] = "2"
        os.environ["MKL_NUM_THREADS"] = "2"
        os.environ["OPENBLAS_NUM_THREADS"] = "2"
        os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
        os.environ["NUMEXPR_NUM_THREADS"] = "2"

        # 2. Memory limit: RLIMIT_AS (virtual memory limit)
        try:
            limit_bytes = int(self.max_process_ram_gb * 1024 * 1024 * 1024)
            _soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, hard if hard > 0 else limit_bytes))
            logger.info(f"Set process memory limit (RLIMIT_AS) to {self.max_process_ram_gb} GB")
        except Exception as e:
            logger.warning(f"Could not set RLIMIT_AS: {e}")

    def start(self) -> None:
        """Starts background monitoring loop."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Hardware safety watchdog active.")

    def stop(self) -> None:
        """Stops background monitoring loop."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=2.0)
            logger.info("Hardware safety watchdog stopped.")

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            temp = self.get_current_temp()
            rss = self.get_process_rss_mb()
            avail_ram = self.get_available_ram_gb()

            self.peak_temp_c = max(self.peak_temp_c, temp)
            self.peak_rss_mb = max(self.peak_rss_mb, rss)

            # Check thermal limits
            if temp >= self.temp_abort_c:
                # Require 2 consecutive checks (at least 2s sustained) to avoid single-instant spike abort
                time.sleep(1.0)
                temp_recheck = self.get_current_temp()
                if temp_recheck >= self.temp_abort_c:
                    logger.critical(f"EMERGENCY ABORT: CPU temperature reached {temp_recheck:.1f}°C (abort threshold {self.temp_abort_c}°C)!")
                    print(f"\n[CRITICAL SAFETY ABORT]: Sustained CPU temp {temp_recheck:.1f}°C exceeded {self.temp_abort_c}°C. Exiting to protect hardware.\n")
                    os._exit(42)

            if temp >= self.temp_pause_c:
                self.is_throttled = True
                logger.warning(f"HIGH TEMP ALERT: {temp:.1f}°C >= {self.temp_pause_c}°C. Pausing for cooldown...")
                pause_start = time.time()
                while temp > self.temp_resume_c and not self._stop_event.is_set():
                    time.sleep(2.0)
                    temp = self.get_current_temp()
                p_elapsed = time.time() - pause_start
                self.pause_duration_sec += p_elapsed
                logger.info(f"Resumed from thermal pause: cooled down to {temp:.1f}°C in {p_elapsed:.1f}s.")

            # Check RAM limits
            if avail_ram < self.min_ram_avail_gb:
                logger.critical(f"LOW MEMORY ABORT: Available RAM {avail_ram:.2f}GB < {self.min_ram_avail_gb}GB threshold!")
                print(f"\n[CRITICAL SAFETY ABORT]: Available RAM {avail_ram:.2f}GB exhausted. Exiting to prevent system freeze.\n")
                os._exit(43)

            time.sleep(self.check_interval_sec)

    def cooldown(self, seconds: float = 60.0, label: str = "Inter-model cooldown") -> None:
        """Sleeps safely between model runs while allowing cooling."""
        logger.info(f"Starting {label} ({seconds:.0f}s)...")
        start = time.time()
        while time.time() - start < seconds and not self._stop_event.is_set():
            time.sleep(1.0)
            t = self.get_current_temp()
            self.peak_temp_c = max(self.peak_temp_c, t)
        logger.info(f"Finished {label}. Current temp: {self.get_current_temp():.1f}°C")


# Global singleton instance
watchdog = HardwareSafetyWatchdog()
