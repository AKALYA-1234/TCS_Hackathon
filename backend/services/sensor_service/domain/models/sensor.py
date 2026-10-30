from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class SensorReadingDomain(BaseModel):
    device_id: str = Field(..., description="Unique hardware or IoT device identifier")
    metric: str = Field(..., description="e.g. temperature, humidity, pressure, power")
    value: float = Field(..., description="Metric numeric scalar value")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None

class SensorReadingEvent(BaseModel):
    event_type: str = "SensorReadingIngested"
    device_id: str
    metric: str
    value: float
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None
