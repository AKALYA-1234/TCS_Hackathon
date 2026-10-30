"""
Simulator Engine for PS 3.2:
- Time-compression speed multiplier (1 real sec = N simulated mins)
- Generates and writes ACTelemetryModel, OccupancyModel, WeatherModel
- Publishes telemetry & occupancy over MQTT (topics: telemetry/{room_id}/{unit_id}, occupancy/{room_id})
- Listens to MQTT commands (topic: cmd/#) and verifies expiry before executing
- Publishes command acknowledgments (topic: cmd_ack/{room_id}/{unit_id})
- Injects anomalies with ground truth stored in ground_truth_labels
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import select, update
from common.database import AsyncSessionLocal
from domain.ac_models import (
    RoomModel, ACUnitModel, ScheduleModel, ACTelemetryModel,
    OccupancyModel, WeatherModel, GroundTruthLabelModel, CommandModel, CommandAckModel
)
from simulator.provider import DatasetProvider, SyntheticProvider, AshraeProvider

logger = logging.getLogger("simulator_engine")


class SimulatorEngine:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        provider_type = os.getenv("DATASET_PROVIDER", "synthetic").lower()
        if provider_type == "ashrae":
            self.provider: DatasetProvider = AshraeProvider()
        else:
            self.provider = SyntheticProvider(seed=42)

        self.is_running = False
        self.speed_multiplier = int(os.getenv("SIMULATOR_SPEED", "60"))  # 1s real = 60s (1 min) sim
        self.simulated_clock = datetime.now(timezone.utc)
        self.injected_anomalies: Dict[str, Dict[str, Any]] = {}  # room_id -> {type, expires_at}
        self.unit_states: Dict[str, Dict[str, Any]] = {}  # unit_id -> {status, set_temp_c}
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info(f"Simulator started with speed multiplier {self.speed_multiplier}x")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Simulator stopped.")

    def set_speed(self, multiplier: int):
        self.speed_multiplier = max(1, min(600, multiplier))
        logger.info(f"Simulator speed set to {self.speed_multiplier}x")

    def reset(self):
        self.stop()
        self.simulated_clock = datetime.now(timezone.utc)
        self.injected_anomalies.clear()
        self.unit_states.clear()
        logger.info("Simulator reset to current UTC time.")

    def inject_anomaly(self, room_id: str, anomaly_type: str, duration_minutes: int = 30):
        expires_at = self.simulated_clock + timedelta(minutes=duration_minutes)
        self.injected_anomalies[room_id] = {
            "type": anomaly_type,
            "start_time": self.simulated_clock,
            "expires_at": expires_at
        }
        logger.warning(f"🚨 Injected anomaly [{anomaly_type}] on room [{room_id}] until {expires_at}")

        # Store in ground truth labels table (completely separate from ML model)
        asyncio.create_task(self._record_ground_truth(room_id, anomaly_type, self.simulated_clock, expires_at))

    async def _record_ground_truth(self, room_id: str, anomaly_type: str, start: datetime, end: datetime):
        try:
            async with AsyncSessionLocal() as session:
                label = GroundTruthLabelModel(
                    room_id=room_id,
                    anomaly_type=anomaly_type,
                    start_time=start,
                    end_time=end,
                    severity=1.0
                )
                session.add(label)
                await session.commit()
        except Exception as e:
            logger.error(f"Error recording ground truth label: {e}")

    def handle_command_message(self, topic: str, payload: dict):
        """
        Receives MQTT command from cmd/{room_id}/{ac_unit_id}.
        Validates expiration timestamp, updates local unit state, and dispatches ack.
        """
        try:
            cmd_id = payload.get("cmd_id")
            room_id = payload.get("room_id")
            unit_id = payload.get("ac_unit_id")
            action = payload.get("action")
            value = payload.get("value")
            expires_at_str = payload.get("expires_at")

            if not unit_id or not action:
                return

            # Check expiration
            is_expired = False
            if expires_at_str:
                exp_dt = datetime.fromisoformat(expires_at_str)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if self.simulated_clock > exp_dt:
                    is_expired = True

            ack_status = "REJECTED_EXPIRED" if is_expired else "APPLIED"

            if not is_expired:
                # Update simulated hardware state
                if unit_id not in self.unit_states:
                    self.unit_states[unit_id] = {"status": "ON", "set_temp_c": 24.0}

                if action == "SHUT_OFF":
                    self.unit_states[unit_id]["status"] = "OFF"
                elif action in ("POWER_ON", "PRE_COOL"):
                    self.unit_states[unit_id]["status"] = "ON"
                    if value is not None:
                        self.unit_states[unit_id]["set_temp_c"] = float(value)
                elif action == "SET_TEMP":
                    self.unit_states[unit_id]["status"] = "ON"
                    if value is not None:
                        self.unit_states[unit_id]["set_temp_c"] = float(value)

                logger.info(f"✅ Simulated AC [{unit_id}] applied action: {action} (Target: {value})")

            # Dispatch MQTT Ack
            ack_payload = {
                "cmd_id": cmd_id,
                "ac_unit_id": unit_id,
                "room_id": room_id,
                "status": ack_status,
                "applied_at": self.simulated_clock.isoformat(),
                "current_status": self.unit_states.get(unit_id, {}).get("status", "OFF"),
                "current_set_temp_c": self.unit_states.get(unit_id, {}).get("set_temp_c", 24.0)
            }

            if self.event_bus:
                self.event_bus.publish(f"cmd_ack/{room_id}/{unit_id}", ack_payload)

            # Record ack in DB
            asyncio.create_task(self._persist_ack(cmd_id, unit_id, ack_status, ack_payload))

        except Exception as e:
            logger.error(f"Error handling simulator command: {e}")

    async def _persist_ack(self, cmd_id: str, unit_id: str, status: str, details: dict):
        if not cmd_id:
            return
        try:
            async with AsyncSessionLocal() as session:
                ack = CommandAckModel(
                    command_id=cmd_id,
                    ac_unit_id=unit_id,
                    status=status,
                    reported_temp_c=details.get("current_set_temp_c"),
                    reported_on_off=details.get("current_status"),
                    details=details
                )
                session.add(ack)
                await session.execute(
                    update(CommandModel)
                    .where(CommandModel.id == cmd_id)
                    .values(status="ACKNOWLEDGED" if status == "APPLIED" else "EXPIRED", ack_received_at=datetime.now(timezone.utc))
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to record command ack: {e}")

    async def _run_loop(self):
        """Simulation tick running every 1 second real-time."""
        while self.is_running:
            try:
                # Advance simulated clock by (1 second * speed_multiplier)
                advance_sec = self.speed_multiplier
                self.simulated_clock += timedelta(seconds=advance_sec)

                # Clean up expired anomalies
                expired = [r for r, d in self.injected_anomalies.items() if self.simulated_clock > d["expires_at"]]
                for r in expired:
                    del self.injected_anomalies[r]

                outdoor_temp = self.provider.get_outdoor_temperature(self.simulated_clock)

                # Fetch rooms and AC units
                async with AsyncSessionLocal() as session:
                    rooms_res = await session.execute(select(RoomModel))
                    rooms = list(rooms_res.scalars().all())

                    units_res = await session.execute(select(ACUnitModel))
                    units = list(units_res.scalars().all())

                    sched_res = await session.execute(select(ScheduleModel))
                    schedules = list(sched_res.scalars().all())

                    # Save outdoor weather
                    weather_rec = WeatherModel(
                        timestamp=self.simulated_clock,
                        outdoor_temp_c=outdoor_temp,
                        relative_humidity=55.0,
                        solar_irradiance_wm2=400.0
                    )
                    session.add(weather_rec)

                    for room in rooms:
                        # Check active schedule
                        dow = self.simulated_clock.weekday()
                        clock_time_str = self.simulated_clock.strftime("%H:%M:%S")
                        sched_active = any(
                            s.room_id == room.id and s.day_of_week == dow and s.start_time <= clock_time_str <= s.end_time
                            for s in schedules
                        )

                        # Simulated Occupancy
                        occupancy_count = self.provider.get_room_occupancy(
                            room.id, self.simulated_clock, room.capacity, sched_active
                        )

                        occ_rec = OccupancyModel(
                            room_id=room.id,
                            timestamp=self.simulated_clock,
                            headcount=occupancy_count,
                            confidence=0.92,
                            is_synthetic=True
                        )
                        session.add(occ_rec)

                        # Publish occupancy to MQTT
                        if self.event_bus:
                            self.event_bus.publish(f"occupancy/{room.id}", {
                                "room_id": room.id,
                                "timestamp": self.simulated_clock.isoformat(),
                                "headcount": occupancy_count,
                                "confidence": 0.92,
                                "is_synthetic": True
                            })

                        # Telemetry per unit in this room
                        room_units = [u for u in units if u.room_id == room.id]
                        injected = self.injected_anomalies.get(room.id, {}).get("type")

                        for unit in room_units:
                            # State defaults
                            if unit.id not in self.unit_states:
                                self.unit_states[unit.id] = {
                                    "status": "ON" if sched_active else "OFF",
                                    "set_temp_c": room.target_temp_c
                                }

                            state = self.unit_states[unit.id]
                            is_on = state["status"] == "ON"
                            set_temp = state["set_temp_c"]

                            calc = self.provider.get_cooling_demand_kw(
                                room_id=room.id,
                                timestamp=self.simulated_clock,
                                rated_kw=unit.rated_kw,
                                occupancy=occupancy_count,
                                capacity=room.capacity,
                                outdoor_temp_c=outdoor_temp,
                                set_temp_c=set_temp,
                                is_on=is_on,
                                injected_anomaly=injected
                            )

                            telem_rec = ACTelemetryModel(
                                room_id=room.id,
                                ac_unit_id=unit.id,
                                timestamp=self.simulated_clock,
                                power_kw=calc["power_kw"],
                                set_temp_c=set_temp,
                                room_temp_c=calc["room_temp_c"],
                                outdoor_temp_c=outdoor_temp,
                                occupancy=occupancy_count,
                                on_off_status=state["status"],
                                scheduled_hours=sched_active
                            )
                            session.add(telem_rec)

                            # Publish telemetry to MQTT
                            if self.event_bus:
                                self.event_bus.publish(f"telemetry/{room.id}/{unit.id}", {
                                    "room_id": room.id,
                                    "ac_unit_id": unit.id,
                                    "timestamp": self.simulated_clock.isoformat(),
                                    "power_kw": calc["power_kw"],
                                    "set_temp_c": set_temp,
                                    "room_temp_c": calc["room_temp_c"],
                                    "outdoor_temp_c": outdoor_temp,
                                    "occupancy": occupancy_count,
                                    "on_off_status": state["status"],
                                    "scheduled_hours": sched_active
                                })

                    await session.commit()

            except Exception as e:
                logger.error(f"Error in simulator loop: {e}")

            await asyncio.sleep(1.0)
