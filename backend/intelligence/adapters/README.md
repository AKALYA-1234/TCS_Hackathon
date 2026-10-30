# ML & Dataset Drop-in Adapters

This directory is the dedicated drop-in zone for supplying real trained ML model weights and the ASHRAE Great Energy Predictor III (GEPIII) dataset.

---

## 1. Dropping in Real ML Models

### Target File Placement
Place your model artifacts in:
- `backend/intelligence/adapters/model_artifacts/`
  - e.g., `baseline_lightgbm.pkl`, `baseline_xgb.onnx`, or `baseline_torch.pt`.

### Required Inference Signature
Your model wrapper must implement `backend.intelligence.baseline.BaselineModel`:
```python
def predict(self, room_id: str, timestamp: datetime, features: Dict[str, Any]) -> Dict[str, float]:
    # Returns:
    # {
    #     "baseline_kw": float,
    #     "lower_bound_kw": float,
    #     "upper_bound_kw": float,
    #     "model_version": str,
    #     "is_placeholder": False
    # }
```

### Environment Switch
Set in `.env`:
```bash
BASELINE_MODEL=custom
BASELINE_MODEL_PATH=/app/intelligence/adapters/model_artifacts/baseline_lightgbm.pkl
```

---

## 2. Dropping in ASHRAE GEPIII Dataset

### Expected Files
Place ASHRAE GEPIII CSVs in `backend/intelligence/adapters/ashrae_data/`:
1. `train.csv` (meter=1 for chilled water, building_id for education buildings)
2. `weather_train.csv` (air_temperature, dew_temperature, cloud_coverage)
3. `building_metadata.csv` (primary_use == "Education", square_feet)

### Environment Switch
Set in `.env`:
```bash
DATASET_PROVIDER=ashrae
ASHRAE_DATA_DIR=/app/intelligence/adapters/ashrae_data
```

The system automatically detects the files upon container start and switches from synthetic sinusoidal generation to reading actual building sub-meter chilled water series.
