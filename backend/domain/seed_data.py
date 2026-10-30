"""
Seed Data Script: Generates 3 Buildings, 15 Diverse Campus Rooms, AC units,
default Schedules, Tariff config, and initial historical telemetry baseline.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from common.database import AsyncSessionLocal, engine, Base
from domain.ac_models import (
    RoomModel, ACUnitModel, ScheduleModel, TariffModel,
    ACTelemetryModel, BaselinePredModel, WasteEventModel,
    ProposalModel, CommandModel, SavingsVerifiedModel, AuditLogModel
)

SEED_ROOMS = [
    # Building 1: Engineering Hall (Lecture halls, technical lab, server room)
    {
        "id": "eng-101",
        "building": "Engineering Hall",
        "name": "Lecture Hall 101",
        "room_type": "lecture_hall",
        "area_sqm": 120.0,
        "capacity": 80,
        "target_temp_c": 24.0,
        "min_temp_c": 23.0,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-eng-101-1", "name": "Cassette Unit 1", "rated_kw": 7.5},
            {"id": "ac-eng-101-2", "name": "Cassette Unit 2", "rated_kw": 7.5},
        ]
    },
    {
        "id": "eng-102",
        "building": "Engineering Hall",
        "name": "Robotics & IoT Lab",
        "room_type": "lab",
        "area_sqm": 90.0,
        "capacity": 35,
        "target_temp_c": 23.0,
        "min_temp_c": 22.0,
        "max_temp_c": 24.5,
        "is_critical": True,  # Critical equipment
        "units": [
            {"id": "ac-eng-102-1", "name": "Precision Split 1", "rated_kw": 6.0},
            {"id": "ac-eng-102-2", "name": "Precision Split 2", "rated_kw": 6.0},
        ]
    },
    {
        "id": "eng-201",
        "building": "Engineering Hall",
        "name": "Seminar Room A",
        "room_type": "seminar",
        "area_sqm": 60.0,
        "capacity": 30,
        "target_temp_c": 24.5,
        "min_temp_c": 23.5,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-eng-201-1", "name": "Wall Mount A", "rated_kw": 4.5},
        ]
    },
    {
        "id": "eng-301",
        "building": "Engineering Hall",
        "name": "Dean & Faculty Office",
        "room_type": "office",
        "area_sqm": 45.0,
        "capacity": 10,
        "target_temp_c": 24.0,
        "min_temp_c": 23.0,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-eng-301-1", "name": "Office Multi-Split", "rated_kw": 3.5},
        ]
    },
    {
        "id": "eng-server",
        "building": "Engineering Hall",
        "name": "Department Server Room",
        "room_type": "lab",
        "area_sqm": 35.0,
        "capacity": 2,
        "target_temp_c": 21.0,
        "min_temp_c": 19.0,
        "max_temp_c": 22.5,
        "is_critical": True,
        "units": [
            {"id": "ac-eng-srv-1", "name": "CRAC Unit 1 (Primary)", "rated_kw": 8.0},
            {"id": "ac-eng-srv-2", "name": "CRAC Unit 2 (Redundant)", "rated_kw": 8.0},
        ]
    },

    # Building 2: Science Complex (Chemistry, Physics, Lecture, Seminar)
    {
        "id": "sci-201",
        "building": "Science Complex",
        "name": "Organic Chemistry Lab",
        "room_type": "lab",
        "area_sqm": 110.0,
        "capacity": 40,
        "target_temp_c": 22.5,
        "min_temp_c": 21.5,
        "max_temp_c": 24.0,
        "is_critical": True,
        "units": [
            {"id": "ac-sci-201-1", "name": "Ducted Packaged 1", "rated_kw": 9.0},
        ]
    },
    {
        "id": "sci-101",
        "building": "Science Complex",
        "name": "Auditorium Hall B",
        "room_type": "lecture_hall",
        "area_sqm": 160.0,
        "capacity": 120,
        "target_temp_c": 24.0,
        "min_temp_c": 23.0,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-sci-101-1", "name": "Chilled Water AHU 1", "rated_kw": 12.0},
            {"id": "ac-sci-101-2", "name": "Chilled Water AHU 2", "rated_kw": 12.0},
        ]
    },
    {
        "id": "sci-305",
        "building": "Science Complex",
        "name": "Physics Computation Lab",
        "room_type": "lab",
        "area_sqm": 75.0,
        "capacity": 30,
        "target_temp_c": 23.5,
        "min_temp_c": 22.5,
        "max_temp_c": 25.0,
        "is_critical": False,
        "units": [
            {"id": "ac-sci-305-1", "name": "Ceiling Inverter", "rated_kw": 5.5},
        ]
    },
    {
        "id": "sci-401",
        "building": "Science Complex",
        "name": "Postgrad Seminar Suite",
        "room_type": "seminar",
        "area_sqm": 50.0,
        "capacity": 25,
        "target_temp_c": 24.5,
        "min_temp_c": 23.5,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-sci-401-1", "name": "Split Inverter 1", "rated_kw": 4.0},
        ]
    },
    {
        "id": "sci-402",
        "building": "Science Complex",
        "name": "Dean of Science Office",
        "room_type": "office",
        "area_sqm": 40.0,
        "capacity": 6,
        "target_temp_c": 24.0,
        "min_temp_c": 23.0,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-sci-402-1", "name": "Split Unit 1", "rated_kw": 3.0},
        ]
    },

    # Building 3: Administration & Management Block
    {
        "id": "adm-101",
        "building": "Administration Block",
        "name": "Executive Council Room",
        "room_type": "seminar",
        "area_sqm": 70.0,
        "capacity": 25,
        "target_temp_c": 23.5,
        "min_temp_c": 22.5,
        "max_temp_c": 25.0,
        "is_critical": False,
        "units": [
            {"id": "ac-adm-101-1", "name": "VRF Indoor A", "rated_kw": 5.0},
            {"id": "ac-adm-101-2", "name": "VRF Indoor B", "rated_kw": 5.0},
        ]
    },
    {
        "id": "adm-201",
        "building": "Administration Block",
        "name": "Finance & Accounts Wing",
        "room_type": "office",
        "area_sqm": 85.0,
        "capacity": 20,
        "target_temp_c": 24.0,
        "min_temp_c": 23.0,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-adm-201-1", "name": "Ductless Split", "rated_kw": 6.0},
        ]
    },
    {
        "id": "adm-202",
        "building": "Administration Block",
        "name": "Registrar Office",
        "room_type": "office",
        "area_sqm": 50.0,
        "capacity": 8,
        "target_temp_c": 24.0,
        "min_temp_c": 23.0,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-adm-202-1", "name": "Office Split", "rated_kw": 3.5},
        ]
    },
    {
        "id": "adm-301",
        "building": "Administration Block",
        "name": "Management Case Study Hall",
        "room_type": "lecture_hall",
        "area_sqm": 100.0,
        "capacity": 60,
        "target_temp_c": 24.0,
        "min_temp_c": 23.0,
        "max_temp_c": 26.0,
        "is_critical": False,
        "units": [
            {"id": "ac-adm-301-1", "name": "Cassette Pack 1", "rated_kw": 6.5},
            {"id": "ac-adm-301-2", "name": "Cassette Pack 2", "rated_kw": 6.5},
        ]
    },
    {
        "id": "adm-archive",
        "building": "Administration Block",
        "name": "Records & Exam Archives",
        "room_type": "office",
        "area_sqm": 40.0,
        "capacity": 4,
        "target_temp_c": 23.0,
        "min_temp_c": 22.0,
        "max_temp_c": 25.0,
        "is_critical": False,
        "units": [
            {"id": "ac-adm-arc-1", "name": "Dehumidifier AC Combo", "rated_kw": 3.0},
        ]
    }
]


async def seed_database():
    """Initializes schema and populates seed campus data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if rooms already exist
        res = await session.execute(select(RoomModel).limit(1))
        if res.scalars().first():
            print("Database already has campus seed data. Skipping room creation.")
            return

        print("🌱 Seeding campus buildings, rooms, AC units, schedules, tariffs...")
        
        # 1. Tariff
        tariff = TariffModel(
            id="default-campus-tariff",
            currency="INR",
            base_rate_per_kwh=8.50,
            peak_rate_per_kwh=12.50,
            peak_start_hour=14,
            peak_end_hour=18,
            setpoint_savings_pct_per_deg=4.0
        )
        session.add(tariff)

        # 2. Rooms and Units
        for r_data in SEED_ROOMS:
            room = RoomModel(
                id=r_data["id"],
                building=r_data["building"],
                name=r_data["name"],
                room_type=r_data["room_type"],
                area_sqm=r_data["area_sqm"],
                capacity=r_data["capacity"],
                target_temp_c=r_data["target_temp_c"],
                min_temp_c=r_data["min_temp_c"],
                max_temp_c=r_data["max_temp_c"],
                is_critical=r_data["is_critical"]
            )
            session.add(room)

            for u_data in r_data["units"]:
                unit = ACUnitModel(
                    id=u_data["id"],
                    room_id=r_data["id"],
                    name=u_data["name"],
                    rated_kw=u_data["rated_kw"],
                    cop=3.2,
                    current_status="OFF",
                    current_set_temp_c=r_data["target_temp_c"]
                )
                session.add(unit)

            # Add default weekday schedule (Monday to Friday, 9:00 - 17:00)
            for dow in range(5):  # Mon-Fri
                sched = ScheduleModel(
                    room_id=r_data["id"],
                    day_of_week=dow,
                    start_time="09:00:00",
                    end_time="17:00:00",
                    activity_name="Regular Academic Hours",
                    expected_headcount=int(r_data["capacity"] * 0.75),
                    enrollment=r_data["capacity"]
                )
                session.add(sched)

        # 3. Add initial sample proposals and audit logs
        now = datetime.now(timezone.utc)
        prop = ProposalModel(
            id="prop-demo-001",
            room_id="eng-101",
            ac_unit_id="ac-eng-101-1",
            action="SET_TEMP",
            target_value=25.0,
            rationale="Ghost cooling detected during empty gap. Pre-cooling adjusted and setpoint relaxed from 22°C to 25°C.",
            estimated_saving_kwh=18.4,
            estimated_saving_inr=192.50,
            source="OPTIMIZER",
            rule_validation_status="PASSED",
            rule_validation_notes="Within ASHRAE 55 comfort band (23-26°C). Non-critical classroom.",
            approval_status="PENDING",
            approval_tier="ONE_CLICK",
            created_at=now - timedelta(minutes=15),
            expires_at=now + timedelta(hours=2)
        )
        session.add(prop)

        audit = AuditLogModel(
            actor="RULE_ENGINE",
            event_type="RULE_VALIDATED",
            entity_id=prop.id,
            details={"status": "PASSED", "comfort_band": "23-26C"}
        )
        session.add(audit)

        await session.commit()
        print(f"✅ Successfully seeded 3 buildings, {len(SEED_ROOMS)} rooms, and default configurations!")


if __name__ == "__main__":
    asyncio.run(seed_database())
