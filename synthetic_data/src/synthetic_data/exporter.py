"""
Exporter and Manifest Writer:
Saves Parquet and CSV files, computes SHA256 hashes, generates manifest.json.
"""
import hashlib
import json
import logging
import os
from typing import Any

import pandas as pd

logger = logging.getLogger("synthetic_data.exporter")


class DataExporter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    @staticmethod
    def sha256_file(filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def export(
        self,
        tables: dict[str, pd.DataFrame],
        master_seed: int,
        config_dict: dict[str, Any]
    ) -> dict[str, Any]:
        file_hashes = {}
        row_counts = {}
        file_sizes = {}

        for table_name, df in tables.items():
            # Parquet export
            parquet_path = os.path.join(self.output_dir, f"{table_name}.parquet")
            df.to_parquet(parquet_path, index=False)
            pq_hash = self.sha256_file(parquet_path)
            file_hashes[f"{table_name}.parquet"] = pq_hash
            file_sizes[f"{table_name}.parquet"] = os.path.getsize(parquet_path)

            # CSV export
            csv_path = os.path.join(self.output_dir, f"{table_name}.csv")
            df.to_csv(csv_path, index=False)
            csv_hash = self.sha256_file(csv_path)
            file_hashes[f"{table_name}.csv"] = csv_hash
            file_sizes[f"{table_name}.csv"] = os.path.getsize(csv_path)

            row_counts[table_name] = len(df)
            logger.info(f"Exported {table_name}: {len(df):,} rows -> {parquet_path}")

        # Compute hash of configuration
        cfg_str = json.dumps(config_dict, sort_keys=True, default=str)
        cfg_hash = hashlib.sha256(cfg_str.encode("utf-8")).hexdigest()

        # Build manifest.json
        manifest = {
            "synthetic": True,
            "transparency_notice": (
                "CRITICAL: All room-level telemetry, occupancy readings, and anomaly labels in this "
                "dataset are SYNTHETIC. Building cooling shapes and weather ambient temperatures are "
                "anchored on actual ASHRAE Great Energy Predictor III meter 1 data (Site 2)."
            ),
            "master_seed": master_seed,
            "config_hash": cfg_hash,
            "ashrae_source_buildings": [173, 253, 229],
            "campus_buildings": ["Engineering Hall", "Science Complex", "Management Block"],
            "resolution_minutes": config_dict.get("time_horizon", {}).get("step_minutes", 5),
            "time_range": {
                "start": config_dict.get("time_horizon", {}).get("start_date"),
                "end": config_dict.get("time_horizon", {}).get("end_date")
            },
            "row_counts": row_counts,
            "file_sizes_bytes": file_sizes,
            "sha256_hashes": file_hashes
        }

        manifest_path = os.path.join(self.output_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Wrote dataset manifest to: {manifest_path}")
        return manifest
