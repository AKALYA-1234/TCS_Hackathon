from typing import Optional
from services.event_bus.mqtt_bus import MqttEventBus
from services.sensor_service.domain.models.sensor import SensorReadingDomain

class SensorEventPublisher:
    def __init__(self, event_bus: MqttEventBus):
        self.bus = event_bus

    def publish_reading_ingested(self, reading: SensorReadingDomain):
        # MQTT Topic Pattern: sensors/{device_id}/{metric}
        topic = f"sensors/{reading.device_id}/{reading.metric}"
        payload = {
            "event": "SensorTelemetryIngested",
            "device_id": reading.device_id,
            "metric": reading.metric,
            "value": reading.value,
            "timestamp": reading.timestamp.isoformat(),
            "metadata": reading.metadata or {}
        }
        self.bus.publish(topic, payload)

    def publish_alert(self, device_id: str, metric: str, value: float, alert_message: str):
        topic = f"alerts/sensors/{device_id}"
        payload = {
            "event": "ThresholdExceededAlert",
            "device_id": device_id,
            "metric": metric,
            "value": value,
            "alert": alert_message
        }
        self.bus.publish(topic, payload)
