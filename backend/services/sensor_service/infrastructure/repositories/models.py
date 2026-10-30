from sqlalchemy import Column, String, Float, DateTime, JSON
from common.database import Base

class SensorTelemetryModel(Base):
    __tablename__ = "sensor_telemetry"

    # TimescaleDB hypertables require primary key to include the partition time column
    device_id = Column(String(100), primary_key=True, index=True)
    metric = Column(String(50), primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), primary_key=True, index=True)
    value = Column(Float, nullable=False)
    device_metadata = Column(JSON, nullable=True)
