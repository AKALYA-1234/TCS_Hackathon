import json
import logging
from typing import Callable, Any
import paho.mqtt.client as mqtt

logger = logging.getLogger("event_bus")

class MqttEventBus:
    def __init__(self, host: str = "mosquitto", port: int = 1883, client_id: str = "fastapi_client"):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self._subscriptions: dict[str, list[Callable[[str, dict], None]]] = {}

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")
            # Re-subscribe to topics
            for topic in self._subscriptions.keys():
                self.client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, code: {rc}")

    def _on_disconnect(self, client, userdata, disconnect_flags, rc, properties=None):
        logger.warning(f"MQTT Disconnected (rc: {rc})")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            payload = {"raw": msg.payload.decode("utf-8", errors="ignore")}

        topic = msg.topic
        for sub_topic, callbacks in self._subscriptions.items():
            if mqtt.topic_matches_sub(sub_topic, topic):
                for cb in callbacks:
                    try:
                        cb(topic, payload)
                    except Exception as e:
                        logger.error(f"Error in MQTT handler for {topic}: {e}")

    def connect(self):
        try:
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to initiate MQTT connection: {e}")

    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting MQTT: {e}")

    def publish(self, topic: str, event_data: dict[str, Any]):
        try:
            payload = json.dumps(event_data)
            self.client.publish(topic, payload, qos=1)
            logger.info(f"Published event to [{topic}]")
        except Exception as e:
            logger.error(f"Failed to publish event to {topic}: {e}")

    def subscribe(self, topic: str, callback: Callable[[str, dict], None]):
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
            if self.client.is_connected():
                self.client.subscribe(topic)
        self._subscriptions[topic].append(callback)
