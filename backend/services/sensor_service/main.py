import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from common.database import engine, Base, initialize_timescale, AsyncSessionLocal
from services.event_bus.mqtt_bus import MqttEventBus
from services.sensor_service.infrastructure.repositories.sensor_repo import SensorTelemetryRepository
from services.sensor_service.presentation.api.router import router as sensor_router
from api.ac_router import router as ac_router
from api.simulation_router import router as simulation_router
from simulator.engine import SimulatorEngine
from domain.seed_data import seed_database

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

event_bus = MqttEventBus(host=MQTT_HOST, port=MQTT_PORT, client_id="sensor_service_publisher")
simulator_engine = SimulatorEngine(event_bus=event_bus)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Start MQTT Client loop
    event_bus.connect()

    # 2. Subscribe simulator to command topics (cmd/#)
    event_bus.subscribe("cmd/#", simulator_engine.handle_command_message)

    # 3. Initialize TimescaleDB Extension & Tables
    await initialize_timescale()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 4. Ensure hypertable is partitioned
    async with AsyncSessionLocal() as session:
        repo = SensorTelemetryRepository(session)
        await repo.initialize_hypertable()

    # 5. Seed Campus Database
    try:
        await seed_database()
    except Exception as e:
        print(f"Seed database warning: {e}")

    # 6. Start Simulator in Background
    simulator_engine.start()

    yield

    # Cleanup
    simulator_engine.stop()
    event_bus.disconnect()

app = FastAPI(
    title="Sensor & IoT Telemetry Microservice (Layered Architecture)",
    version="2.0.0",
    description="Event-Driven TimescaleDB time-series ingestion, AC usage optimization & simulator",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.ac_router import (
    router as ac_router, get_unit_history, get_all_units_swimlanes,
    get_optimizer_room_recommendation, preview_optimizer_schedule,
    create_proposal, list_proposals
)
from fastapi import APIRouter

root_history_router = APIRouter(tags=["History & Optimizer Direct"])
root_history_router.add_api_route("/history/unit/{unit_id}", get_unit_history, methods=["GET"])
root_history_router.add_api_route("/api/history/unit/{unit_id}", get_unit_history, methods=["GET"])
root_history_router.add_api_route("/history/swimlanes", get_all_units_swimlanes, methods=["GET"])
root_history_router.add_api_route("/api/history/swimlanes", get_all_units_swimlanes, methods=["GET"])

# Optimizer & Proposals direct routes
root_history_router.add_api_route("/optimizer/room/{room_id}/recommendation", get_optimizer_room_recommendation, methods=["GET"])
root_history_router.add_api_route("/api/optimizer/room/{room_id}/recommendation", get_optimizer_room_recommendation, methods=["GET"])
root_history_router.add_api_route("/optimizer/room/{room_id}/preview", preview_optimizer_schedule, methods=["POST"])
root_history_router.add_api_route("/api/optimizer/room/{room_id}/preview", preview_optimizer_schedule, methods=["POST"])
root_history_router.add_api_route("/proposals", list_proposals, methods=["GET"])
root_history_router.add_api_route("/proposals", create_proposal, methods=["POST"])
root_history_router.add_api_route("/api/proposals", list_proposals, methods=["GET"])
root_history_router.add_api_route("/api/proposals", create_proposal, methods=["POST"])

app.include_router(sensor_router)
app.include_router(ac_router)
app.include_router(simulation_router)
app.include_router(root_history_router)

@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "online",
            "service": "sensor_service",
            "database": "timescaledb_connected",
            "mqtt_connected": event_bus.client.is_connected(),
            "simulator_running": simulator_engine.is_running,
            "simulated_clock": simulator_engine.simulated_clock.isoformat()
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e)}

