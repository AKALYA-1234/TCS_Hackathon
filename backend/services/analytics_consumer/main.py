import os
import json
import logging
from collections import deque
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from services.event_bus.mqtt_bus import MqttEventBus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analytics_consumer")

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

event_bus = MqttEventBus(host=MQTT_HOST, port=MQTT_PORT, client_id="analytics_consumer_worker")

# In-memory circular buffer of latest events and alerts for connected dashboard clients
recent_events = deque(maxlen=100)
active_alerts = deque(maxlen=50)
connected_clients: list[WebSocket] = []

def handle_sensor_telemetry(topic: str, payload: dict):
    event_entry = {
        "id": f"evt-{len(recent_events)+1}",
        "topic": topic,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
    recent_events.appendleft(event_entry)
    logger.info(f"⚡ [Event Processed] Topic: {topic} | Metric: {payload.get('metric')} = {payload.get('value')}")

def handle_sensor_alert(topic: str, payload: dict):
    alert_entry = {
        "id": f"alt-{len(active_alerts)+1}",
        "topic": topic,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
    active_alerts.appendleft(alert_entry)
    logger.warning(f"🚨 [ALERT CONSUMED] {payload.get('alert')}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Connect to MQTT
    event_bus.connect()

    # 2. Subscribe to event topics (Wildcard pattern matching)
    event_bus.subscribe("sensors/#", handle_sensor_telemetry)
    event_bus.subscribe("alerts/#", handle_sensor_alert)
    logger.info("Subscribed to MQTT topics: sensors/# and alerts/#")

    yield

    event_bus.disconnect()

app = FastAPI(
    title="Event-Driven Analytics & Stream Consumer",
    version="2.0.0",
    description="Asynchronous event subscriber consuming MQTT sensor streams and publishing real-time metrics",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "status": "online",
        "service": "analytics_consumer",
        "mqtt_connected": event_bus.client.is_connected(),
        "events_in_buffer": len(recent_events),
        "alerts_in_buffer": len(active_alerts)
    }

@app.get("/events/stream")
async def get_recent_stream(limit: int = 50):
    return list(recent_events)[:limit]

@app.get("/events/alerts")
async def get_active_alerts(limit: int = 20):
    return list(active_alerts)[:limit]
