from services.sensor_service.domain.models.sensor import SensorReadingDomain
from services.sensor_service.infrastructure.repositories.sensor_repo import SensorTelemetryRepository
from services.sensor_service.infrastructure.events.publisher import SensorEventPublisher

class IngestSensorReadingUseCase:
    """
    Application Use Case orchestrating:
    1. Domain validation
    2. TimescaleDB hypertable persistence
    3. Asynchronous MQTT event publishing to broker
    4. Anomaly detection & Alert triggering
    """
    def __init__(self, repository: SensorTelemetryRepository, publisher: SensorEventPublisher):
        self.repository = repository
        self.publisher = publisher

    async def execute(self, reading_data: SensorReadingDomain) -> dict:
        # 1. Persist to TimescaleDB
        saved_record = await self.repository.save(reading_data)

        # 2. Publish Event to MQTT broker for consumers / subscribers
        self.publisher.publish_reading_ingested(reading_data)

        # 3. Domain Logic: threshold anomaly evaluation
        anomaly_detected = False
        if reading_data.metric == "temperature" and reading_data.value > 85.0:
            anomaly_detected = True
            self.publisher.publish_alert(
                device_id=reading_data.device_id,
                metric=reading_data.metric,
                value=reading_data.value,
                alert_message=f"Critical high temperature: {reading_data.value}°C exceeds safety threshold (85°C)!"
            )
        elif reading_data.metric == "pressure" and reading_data.value > 120.0:
            anomaly_detected = True
            self.publisher.publish_alert(
                device_id=reading_data.device_id,
                metric=reading_data.metric,
                value=reading_data.value,
                alert_message=f"Overpressure warning: {reading_data.value} PSI exceeds limit!"
            )

        return {
            "status": "ingested",
            "device_id": saved_record.device_id,
            "metric": saved_record.metric,
            "value": saved_record.value,
            "timestamp": saved_record.timestamp.isoformat(),
            "anomaly_detected": anomaly_detected
        }
