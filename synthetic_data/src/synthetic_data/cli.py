"""
Command Line Interface for synthetic_data package.
"""
import logging
import os
import sys

import click
import pandas as pd
import yaml

from synthetic_data.exporter import DataExporter
from synthetic_data.generator import SyntheticDataGenerator
from synthetic_data.streamer import TelemetryStreamer
from synthetic_data.validator import DataValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("synthetic_data.cli")


@click.group()
def main():
    """PS 3.2 Room-Level Synthetic AC Telemetry Generator"""


@main.command()
@click.option("--config", default="config/default.yaml", help="Path to default.yaml")
@click.option("--rooms", default="config/rooms.yaml", help="Path to rooms.yaml")
@click.option("--anomalies", default="config/anomalies.yaml", help="Path to anomalies.yaml")
@click.option("--output-dir", default="output", help="Directory for generated Parquet/CSV")
def generate(config, rooms, anomalies, output_dir):
    """Generate synthetic AC telemetry, occupancy, weather, and counterfactuals."""
    base_dir = os.getcwd()
    if not os.path.isabs(config):
        config = os.path.join(base_dir, config)
    if not os.path.isabs(rooms):
        rooms = os.path.join(base_dir, rooms)
    if not os.path.isabs(anomalies):
        anomalies = os.path.join(base_dir, anomalies)
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(base_dir, output_dir)

    generator = SyntheticDataGenerator(
        default_config_path=config,
        rooms_config_path=rooms,
        anomalies_config_path=anomalies
    )

    tables = generator.generate()

    with open(config, "r", encoding="utf-8") as f:
        cfg_dict = yaml.safe_load(f)

    exporter = DataExporter(output_dir)
    manifest = exporter.export(tables, master_seed=generator.seed, config_dict=cfg_dict)

    click.secho(
        f"Successfully generated {manifest['row_counts']['ac_telemetry']:,} telemetry records. "
        f"Exported to {output_dir} with manifest.json",
        fg="green", bold=True
    )


@main.command()
@click.option("--output-dir", default="output", help="Directory containing Parquet files to validate")
def validate(output_dir):
    """Validate generated datasets and write VALIDATION.md with measured data."""
    base_dir = os.getcwd()
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(base_dir, output_dir)

    validator = DataValidator(output_dir)
    is_valid, errors, _report = validator.validate_and_report()

    if is_valid:
        click.secho("ALL VALIDATION CHECKS PASSED: 0 errors detected. Wrote VALIDATION.md", fg="green", bold=True)
    else:
        click.secho(f"Validation FAILED with {len(errors)} errors (see VALIDATION.md):", fg="red", bold=True)
        for err in errors:
            click.echo(f"  - {err}")
        sys.exit(1)


@main.command()
@click.option("--output-dir", default="output", help="Directory containing Parquet files")
@click.option("--speed", default=60.0, help="Speed multiplier (e.g. 60x for 1 sec = 1 min)")
@click.option("--limit", default=30, help="Max records to stream")
@click.option("--mqtt", is_flag=True, default=False, help="Enable MQTT publishing")
def stream(output_dir, speed, limit, mqtt):
    """Stream synthetic telemetry as JSON lines to stdout or MQTT broker."""
    base_dir = os.getcwd()
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(base_dir, output_dir)

    pq_file = os.path.join(output_dir, "ac_telemetry.parquet")
    streamer = TelemetryStreamer(pq_file, speed_multiplier=speed, enable_mqtt=mqtt)
    streamer.stream(limit=limit)


@main.command()
@click.option("--output-dir", default="output", help="Directory containing Parquet files")
def summary(output_dir):
    """Show descriptive summary of generated synthetic data."""
    base_dir = os.getcwd()
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(base_dir, output_dir)

    telem_path = os.path.join(output_dir, "ac_telemetry.parquet")
    if not os.path.exists(telem_path):
        click.secho(f"File {telem_path} not found. Run generate first.", fg="red")
        return

    df = pd.read_parquet(telem_path)
    click.echo("\n--- AC MAIN TELEMETRY SUMMARY ---")
    click.echo(f"Total Rows: {len(df):,}")
    click.echo(f"Time Range: {df['date_time'].min()} to {df['date_time'].max()}")
    click.echo(f"Unique Rooms: {df['room'].nunique()}")
    click.echo(f"Unique AC Units: {df['ac_unit_id'].nunique()}")
    click.echo(f"Total Energy Consumed: {df['power_kw'].sum() * (5.0 / 60.0):,.2f} kWh")
    click.echo(f"Mean Power (when ON): {df[df['on_off_status'] == 'ON']['power_kw'].mean():.2f} kW")
    click.echo(f"Mean Indoor Temp: {df['room_temp_c'].mean():.1f} °C")

    gt_path = os.path.join(output_dir, "ground_truth_labels.parquet")
    if os.path.exists(gt_path):
        gt = pd.read_parquet(gt_path)
        click.echo("\n--- GROUND TRUTH ANOMALIES & DECOYS ---")
        click.echo(f"Total Injected Events: {len(gt):,}")
        click.echo(gt["anomaly_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
