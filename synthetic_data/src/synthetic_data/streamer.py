"""
Streamer module:
Replays synthetic telemetry as JSON lines with speed multiplier, with optional MQTT publishing.
Dry-run default.
"""
import json
import logging
import os
import time

import click
import pandas as pd

logger = logging.getLogger("synthetic_data.streamer")


class TelemetryStreamer:
    def __init__(
        self,
        parquet_file: str,
        speed_multiplier: float = 60.0,
        enable_mqtt: bool = False,
        mqtt_host: str = "localhost",
        mqtt_port: int = 1883
    ):
        self.parquet_file = parquet_file
        self.speed_multiplier = max(1.0, speed_multiplier)
        self.enable_mqtt = enable_mqtt
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_client = None

        if self.enable_mqtt:
            try:
                import paho.mqtt.client as mqtt  # type: ignore[import-untyped, import-not-found] # pyright: ignore[reportMissingImports]
                self.mqtt_client = mqtt.Client()
                self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
                logger.info(f"Connected to MQTT broker at {mqtt_host}:{mqtt_port}")
            except Exception as e:
                logger.warning(f"Could not connect to MQTT broker ({e}). Falling back to dry-run streaming.")
                self.enable_mqtt = False

    def stream(self, limit: int | None = 50):
        if not os.path.exists(self.parquet_file):
            raise FileNotFoundError(f"Telemetry parquet not found at: {self.parquet_file}")

        df = pd.read_parquet(self.parquet_file)
        logger.info(f"Loaded {len(df):,} telemetry records to replay at {self.speed_multiplier}x speed...")

        count = 0
        for row in df.itertuples():
            rm = str(getattr(row, "room"))  # noqa: B009
            uid = str(getattr(row, "ac_unit_id"))  # noqa: B009
            payload = {
                "room": rm,
                "ac_unit_id": uid,
                "date_time": str(getattr(row, "date_time")),  # noqa: B009
                "power_kw": float(getattr(row, "power_kw")),  # noqa: B009
                "set_temp_c": float(getattr(row, "set_temp_c")),  # noqa: B009
                "room_temp_c": float(getattr(row, "room_temp_c")),  # noqa: B009
                "occupancy": int(getattr(row, "occupancy")),  # noqa: B009
                "on_off_status": str(getattr(row, "on_off_status")),  # noqa: B009
                "scheduled_hours": bool(getattr(row, "scheduled_hours"))  # noqa: B009
            }

            line = json.dumps(payload)
            click.echo(line)

            if self.enable_mqtt and self.mqtt_client:
                topic = f"telemetry/{rm}/{uid}"
                self.mqtt_client.publish(topic, line)

            count += 1
            if limit and count >= limit:
                break

            # Sleep scaled by speed multiplier (simulated 5 minutes = 300s / multiplier)
            sleep_sec = 300.0 / self.speed_multiplier
            # Small realistic sleep capped for CLI responsiveness
            time.sleep(min(0.05, sleep_sec))
