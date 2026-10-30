from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, text
from services.sensor_service.domain.models.sensor import SensorReadingDomain
from services.sensor_service.infrastructure.repositories.models import SensorTelemetryModel

class SensorTelemetryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_hypertable(self):
        """Converts sensor_telemetry table into a TimescaleDB hypertable partitioned on timestamp."""
        try:
            await self.db.execute(text(
                "SELECT create_hypertable('sensor_telemetry', 'timestamp', if_not_exists => TRUE);"
            ))
            await self.db.commit()
        except Exception:
            await self.db.rollback()

    async def save(self, reading: SensorReadingDomain) -> SensorTelemetryModel:
        record = SensorTelemetryModel(
            device_id=reading.device_id,
            metric=reading.metric,
            timestamp=reading.timestamp,
            value=reading.value,
            device_metadata=reading.metadata
        )
        self.db.add(record)
        await self.db.commit()
        return record

    async def get_latest_readings(self, device_id: Optional[str] = None, limit: int = 50) -> List[SensorTelemetryModel]:
        query = select(SensorTelemetryModel).order_by(desc(SensorTelemetryModel.timestamp)).limit(limit)
        if device_id:
            query = query.where(SensorTelemetryModel.device_id == device_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_aggregates(self, metric: Optional[str] = None):
        """TimescaleDB time_bucket analytical aggregation query."""
        sql = text("""
            SELECT 
                time_bucket('1 minute', timestamp) AS bucket,
                metric,
                AVG(value) AS avg_value,
                MAX(value) AS max_value,
                MIN(value) AS min_value,
                COUNT(*) AS total_points
            FROM sensor_telemetry
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            GROUP BY bucket, metric
            ORDER BY bucket DESC
            LIMIT 20;
        """)
        result = await self.db.execute(sql)
        rows = result.mappings().all()
        return [dict(r) for r in rows]
