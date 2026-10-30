from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from common.database import get_db
from services.sensor_service.domain.models.sensor import SensorReadingDomain
from services.sensor_service.infrastructure.repositories.sensor_repo import SensorTelemetryRepository
from services.sensor_service.infrastructure.events.publisher import SensorEventPublisher
from services.sensor_service.application.use_cases.ingest_reading import IngestSensorReadingUseCase

router = APIRouter(prefix="/sensors", tags=["Sensors & Telemetry"])

# We inject the publisher from the running app state
def get_sensor_publisher():
    from services.sensor_service.main import event_bus
    return SensorEventPublisher(event_bus)

@router.post("/readings", status_code=201)
async def ingest_sensor_reading(
    reading: SensorReadingDomain,
    db: AsyncSession = Depends(get_db),
    publisher: SensorEventPublisher = Depends(get_sensor_publisher)
):
    """
    Ingests a time-series telemetry reading into TimescaleDB and broadcasts it via MQTT event topic.
    """
    repo = SensorTelemetryRepository(db)
    use_case = IngestSensorReadingUseCase(repo, publisher)
    return await use_case.execute(reading)

@router.get("/readings")
async def get_latest_sensor_readings(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    repo = SensorTelemetryRepository(db)
    records = await repo.get_latest_readings(device_id=device_id, limit=limit)
    return [
        {
            "device_id": r.device_id,
            "metric": r.metric,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "value": r.value,
            "metadata": r.device_metadata
        }
        for r in records
    ]

@router.get("/analytics/time-buckets")
async def get_time_bucket_analytics(
    metric: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a TimescaleDB analytical query aggregating time_bucket('1 minute') averages, mins, and maxes.
    """
    repo = SensorTelemetryRepository(db)
    return await repo.get_aggregates(metric=metric)
