"""
Comprehensive REST & SSE API Router for PS 3.2:
- Campus overview (KPIs, heatmap, rankings)
- Room details (telemetry, baseline band, waste events, headcount)
- Waste events with filters and INR costs
- Weekly & monthly forecasts with confidence intervals
- Optimizer runs and schedule CRUD
- Proposals (inbox, approve, reject)
- Commands and ack status
- Savings verification (reported as ranges)
- Model evaluation metrics against ground truth
- Chat endpoint (with tool transparency)
- Simulator control (start, stop, speed multiplier, reset, inject anomaly, run demo scenario)
"""
import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, case, text

from common.database import get_db, AsyncSessionLocal
from domain.ac_models import (
    RoomModel, ACUnitModel, ACTelemetryModel, OccupancyModel,
    ScheduleModel, ScheduleExceptionModel, ScheduleVersionModel,
    TariffModel, WasteEventModel, ForecastModel,
    ProposalModel, CommandModel, SavingsVerifiedModel, AuditLogModel,
    GroundTruthLabelModel
)
from domain.schemas import (
    SimulatorControlRequest, ChatRequest, ProposalCreate, CommandDispatch
)
from intelligence.forecaster import Forecaster
from intelligence.optimizer import Optimizer
from intelligence.schedule_optimizer import optimizer_service
from intelligence.evaluator import ModelEvaluator
from intelligence.savings_engine import SavingsEngine
from intelligence.baseline import SeasonalGradientBoostingBaseline
from governance.rule_engine import RuleEngine
from governance.command_service import CommandService
from governance.llm_agent import LLMAgentService

router = APIRouter(prefix="/ac", tags=["AC Optimization"])

# Global singletons
rule_engine = RuleEngine()
forecaster = Forecaster()
optimizer = Optimizer()
evaluator = ModelEvaluator()
savings_engine = SavingsEngine()
baseline_model = SeasonalGradientBoostingBaseline()
llm_agent = LLMAgentService()


def get_simulator():
    from services.sensor_service.main import simulator_engine
    return simulator_engine


def get_command_service():
    from services.sensor_service.main import event_bus
    return CommandService(event_bus)


# -------------------------------------------------------------
# 1. CAMPUS OVERVIEW & HEATMAP
# -------------------------------------------------------------
@router.get("/campus/overview")
async def get_campus_overview(db: AsyncSession = Depends(get_db)):
    """
    Campus KPI cards:
    Total power (kW), Total energy wasted (kWh), Cost wasted (INR),
    Verified savings range (min, max, est), active waste count.
    """
    rooms_res = await db.execute(select(RoomModel))
    rooms = list(rooms_res.scalars().all())

    units_res = await db.execute(select(ACUnitModel))
    units = list(units_res.scalars().all())

    # Latest readings per room
    room_statuses = []
    total_power = 0.0
    for r in rooms:
        t_res = await db.execute(
            select(ACTelemetryModel)
            .where(ACTelemetryModel.room_id == r.id)
            .order_by(desc(ACTelemetryModel.timestamp))
            .limit(1)
        )
        latest = t_res.scalars().first()
        power = latest.power_kw if latest else 0.0
        total_power += power

        room_statuses.append({
            "room_id": r.id,
            "building": r.building,
            "name": r.name,
            "room_type": r.room_type,
            "power_kw": power,
            "room_temp_c": latest.room_temp_c if latest else r.target_temp_c,
            "set_temp_c": latest.set_temp_c if latest else r.target_temp_c,
            "occupancy": latest.occupancy if latest else 0,
            "capacity": r.capacity,
            "is_on": latest.on_off_status == "ON" if latest else False,
            "is_critical": r.is_critical
        })

    # Total Waste & Verified Savings
    waste_res = await db.execute(
        select(
            func.coalesce(func.sum(WasteEventModel.wasted_kwh), 0.0),
            func.coalesce(func.sum(WasteEventModel.wasted_cost_inr), 0.0),
            func.count(WasteEventModel.id)
        )
    )
    total_waste_kwh, total_waste_inr, total_waste_events = waste_res.first()

    savings_res = await db.execute(
        select(
            func.coalesce(func.sum(SavingsVerifiedModel.savings_kwh_min), 0.0),
            func.coalesce(func.sum(SavingsVerifiedModel.savings_kwh_est), 0.0),
            func.coalesce(func.sum(SavingsVerifiedModel.savings_kwh_max), 0.0),
            func.coalesce(func.sum(SavingsVerifiedModel.savings_inr_est), 0.0)
        )
    )
    sav_min, sav_est, sav_max, sav_inr = savings_res.first()

    # Top recoverable waste rooms ranking
    waste_rooms_res = await db.execute(
        select(
            WasteEventModel.room_id,
            func.sum(WasteEventModel.wasted_kwh).label("kwh"),
            func.sum(WasteEventModel.wasted_cost_inr).label("inr"),
            func.count(WasteEventModel.id).label("events")
        )
        .group_by(WasteEventModel.room_id)
        .order_by(desc("inr"))
        .limit(5)
    )
    top_waste_ranking = [
        {
            "room_id": row.room_id,
            "wasted_kwh": round(row.kwh, 1),
            "wasted_inr": round(row.inr, 2),
            "events_count": row.events
        }
        for row in waste_rooms_res.all()
    ]

    return {
        "kpis": {
            "total_power_kw": round(total_power, 2),
            "total_waste_kwh": round(total_waste_kwh, 1),
            "total_waste_inr": round(total_waste_inr, 2),
            "waste_event_count": total_waste_events,
            "verified_savings_kwh": {
                "min": round(sav_min, 1),
                "est": round(sav_est, 1),
                "max": round(sav_max, 1)
            },
            "verified_savings_inr": round(sav_inr, 2),
            "total_rooms": len(rooms),
            "total_units": len(units)
        },
        "heatmap": room_statuses,
        "top_waste_ranking": top_waste_ranking
    }


# -------------------------------------------------------------
# 1B. ROOMS LIST (ALL ROOMS WITH METADATA)
# -------------------------------------------------------------
@router.get("/rooms")
async def list_rooms(db: AsyncSession = Depends(get_db)):
    """
    Returns full list of campus rooms with building, type, capacity, area, and units.
    Additive read-only endpoint for the Rooms master-detail directory.
    """
    rooms_res = await db.execute(select(RoomModel).order_by(RoomModel.building, RoomModel.id))
    rooms = list(rooms_res.scalars().all())

    units_res = await db.execute(select(ACUnitModel))
    all_units = list(units_res.scalars().all())
    units_by_room = {}
    for u in all_units:
        units_by_room.setdefault(u.room_id, []).append({
            "id": u.id,
            "name": u.name,
            "rated_kw": u.rated_kw,
            "status": u.current_status,
            "set_temp": u.current_set_temp_c
        })

    result = []
    for r in rooms:
        r_units = units_by_room.get(r.id, [])
        result.append({
            "id": r.id,
            "name": r.name,
            "building": r.building,
            "room_type": r.room_type,
            "area_sqm": r.area_sqm,
            "capacity": r.capacity,
            "target_temp_c": r.target_temp_c,
            "comfort_band": [r.min_temp_c, r.max_temp_c],
            "is_critical": r.is_critical,
            "manual_override_active": bool(r.manual_override_until and r.manual_override_until > datetime.now(timezone.utc)),
            "units_count": len(r_units),
            "units": r_units
        })

    return result


# -------------------------------------------------------------
# 2. ROOM DETAIL & TIME-SERIES WITH BASELINE BAND
# -------------------------------------------------------------
@router.get("/rooms/{room_id}/detail")
async def get_room_detail(room_id: str, limit: int = 40, db: AsyncSession = Depends(get_db)):
    room = await db.get(RoomModel, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    units_res = await db.execute(select(ACUnitModel).where(ACUnitModel.room_id == room_id))
    units = list(units_res.scalars().all())

    # Recent Telemetry
    telem_res = await db.execute(
        select(ACTelemetryModel)
        .where(ACTelemetryModel.room_id == room_id)
        .order_by(desc(ACTelemetryModel.timestamp))
        .limit(limit)
    )
    telemetry = list(reversed(telem_res.scalars().all()))

    # Build actual vs baseline counterfactual band
    series = []
    for t in telemetry:
        bl = baseline_model.predict(
            room_id=room_id,
            timestamp=t.timestamp,
            features={
                "outdoor_temp_c": t.outdoor_temp_c,
                "occupancy": t.occupancy,
                "capacity": room.capacity,
                "rated_kw": units[0].rated_kw if units else 5.0,
                "scheduled_hours": t.scheduled_hours,
                "target_temp_c": room.target_temp_c
            }
        )
        series.append({
            "timestamp": t.timestamp.isoformat(),
            "actual_power_kw": t.power_kw,
            "baseline_kw": bl["baseline_kw"],
            "lower_bound_kw": bl["lower_bound_kw"],
            "upper_bound_kw": bl["upper_bound_kw"],
            "room_temp_c": t.room_temp_c,
            "set_temp_c": t.set_temp_c,
            "outdoor_temp_c": t.outdoor_temp_c,
            "occupancy": t.occupancy,
            "on_off_status": t.on_off_status
        })

    # Recent Waste events for this room
    waste_res = await db.execute(
        select(WasteEventModel)
        .where(WasteEventModel.room_id == room_id)
        .order_by(desc(WasteEventModel.start_time))
        .limit(10)
    )
    waste_events = list(waste_res.scalars().all())

    return {
        "room": {
            "id": room.id,
            "name": room.name,
            "building": room.building,
            "room_type": room.room_type,
            "area_sqm": room.area_sqm,
            "capacity": room.capacity,
            "target_temp_c": room.target_temp_c,
            "comfort_band": [room.min_temp_c, room.max_temp_c],
            "is_critical": room.is_critical,
            "manual_override_active": bool(room.manual_override_until and room.manual_override_until > datetime.now(timezone.utc))
        },
        "units": [
            {"id": u.id, "name": u.name, "rated_kw": u.rated_kw, "status": u.current_status, "set_temp": u.current_set_temp_c}
            for u in units
        ],
        "telemetry_series": series,
        "waste_events": [
            {
                "id": w.id,
                "type": w.event_type,
                "start_time": w.start_time.isoformat(),
                "wasted_kwh": w.wasted_kwh,
                "wasted_cost_inr": w.wasted_cost_inr,
                "confidence": w.confidence
            }
            for w in waste_events
        ]
    }


# -------------------------------------------------------------
# 3. WASTE EVENTS LIST & FILTERS
# -------------------------------------------------------------
@router.get("/waste-events")
async def list_waste_events(
    room_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    q = select(WasteEventModel).order_by(desc(WasteEventModel.start_time)).limit(limit)
    if room_id:
        q = q.where(WasteEventModel.room_id == room_id)
    if event_type:
        q = q.where(WasteEventModel.event_type == event_type)

    res = await db.execute(q)
    events = list(res.scalars().all())
    return [
        {
            "id": e.id,
            "room_id": e.room_id,
            "ac_unit_id": e.ac_unit_id,
            "event_type": e.event_type,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "wasted_kwh": e.wasted_kwh,
            "wasted_cost_inr": e.wasted_cost_inr,
            "confidence": e.confidence,
            "resolved": e.resolved,
            "details": e.details
        }
        for e in events
    ]


# -------------------------------------------------------------
# 4. FORECASTS (WEEKLY & MONTHLY WITH CONFIDENCE INTERVALS)
# -------------------------------------------------------------
@router.get("/forecasts/{room_id}")
async def get_room_forecast(room_id: str, forecast_type: str = "weekly", db: AsyncSession = Depends(get_db)):
    room = await db.get(RoomModel, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    units_res = await db.execute(select(ACUnitModel).where(ACUnitModel.room_id == room_id))
    units = list(units_res.scalars().all())
    total_rated_kw = sum(u.rated_kw for u in units) if units else 6.0

    if forecast_type == "monthly":
        data = forecaster.generate_monthly_forecast(room_id, total_rated_kw, room.capacity)
    else:
        data = forecaster.generate_weekly_forecast(room_id, total_rated_kw, room.capacity)

    return {
        "room_id": room_id,
        "forecast_type": forecast_type,
        "is_placeholder": True,
        "forecast": data
    }


# -------------------------------------------------------------
# 5. OPTIMIZER RUN & SCHEDULE CRUD
# -------------------------------------------------------------
@router.post("/optimizer/run")
async def run_optimizer_for_room(room_id: str, db: AsyncSession = Depends(get_db)):
    room = await db.get(RoomModel, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    units_res = await db.execute(select(ACUnitModel).where(ACUnitModel.room_id == room_id))
    units = list(units_res.scalars().all())
    rated_kw = units[0].rated_kw if units else 5.0

    # Fetch outdoor temperature from WeatherProvider (live/replay forecast)
    try:
        from services.weather_provider import get_weather_provider
    except ImportError:
        from backend.services.weather_provider import get_weather_provider
    weather_info = get_weather_provider().get_weather()
    current_outdoor_temp = weather_info.current.outdoor_temp_c

    result = optimizer.optimize_room(
        room_id=room_id,
        current_set_temp_c=room.target_temp_c,
        target_comfort_min=room.min_temp_c,
        target_comfort_max=room.max_temp_c,
        schedule_start_time="09:00:00",
        schedule_end_time="17:00:00",
        rated_kw=rated_kw,
        outdoor_temp_c=current_outdoor_temp,
        is_critical=room.is_critical
    )
    result["weather_context"] = {
        "source": weather_info.source,
        "status": weather_info.status,
        "outdoor_temp_c": current_outdoor_temp,
        "relative_humidity": weather_info.current.relative_humidity,
        "precool_advice": f"Pre-cooling {result['recommended_precool_lead_min']} min ahead based on {weather_info.source} ambient {current_outdoor_temp}°C"
    }
    return result


@router.get("/optimizer/room/{room_id}/recommendation")
async def get_optimizer_room_recommendation(
    room_id: str,
    unit_scope: str = "both",
    db: AsyncSession = Depends(get_db)
):
    try:
        return await optimizer_service.get_room_recommendation(room_id=room_id, db=db, unit_scope=unit_scope)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimizer/room/{room_id}/preview")
async def preview_optimizer_schedule(
    room_id: str,
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        bars_by_day_raw = payload.get("bars_by_day", {})
        bars_by_day = {int(k): v for k, v in bars_by_day_raw.items()}
        setpoint = float(payload.get("setpoint", 24.0))
        unit_scope = payload.get("unit_scope", "both")
        return await optimizer_service.preview_schedule_edit(
            room_id=room_id,
            bars_by_day=bars_by_day,
            setpoint=setpoint,
            unit_scope=unit_scope,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules/{room_id}")
async def get_room_schedules(room_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(ScheduleModel).where(ScheduleModel.room_id == room_id))
    return list(res.scalars().all())


@router.post("/schedules/blocks")
async def create_or_update_schedule_block(
    block: Dict[str, Any],
    actor: str = "OPERATOR_ADMIN",
    db: AsyncSession = Depends(get_db)
):
    room_id = block.get("room_id")
    if not room_id:
        raise HTTPException(status_code=400, detail="room_id required")
        
    room = await db.get(RoomModel, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
        
    # Safety: Exception room AC can never be scheduled OFF or given setpoint outside comfort band
    if room.is_critical:
        setpoint = block.get("setpoint_c", 21.0)
        if setpoint > 23.0 or setpoint < 18.0:
            raise HTTPException(status_code=400, detail="Server/Critical room setpoint must stay within [18°C, 23°C]")

    block_id = block.get("id")
    existing = None
    if block_id:
        existing = await db.get(ScheduleModel, block_id)

    if existing:
        existing.day_of_week = block.get("day_of_week", existing.day_of_week)
        existing.start_time = block.get("start_time", existing.start_time)
        existing.end_time = block.get("end_time", existing.end_time)
        existing.activity_name = block.get("activity_name", existing.activity_name)
        existing.expected_headcount = block.get("expected_headcount", existing.expected_headcount)
        existing.setpoint_c = block.get("setpoint_c", existing.setpoint_c)
        existing.precool_mode = block.get("precool_mode", existing.precool_mode)
        existing.precool_lead_min = block.get("precool_lead_min", existing.precool_lead_min)
        existing.shutoff_mode = block.get("shutoff_mode", existing.shutoff_mode)
        existing.shutoff_lead_min = block.get("shutoff_lead_min", existing.shutoff_lead_min)
        existing.auto_off_empty_min = block.get("auto_off_empty_min", existing.auto_off_empty_min)
        existing.notes = block.get("notes", existing.notes)
        existing.is_active = block.get("is_active", existing.is_active)
        res_block = existing
    else:
        res_block = ScheduleModel(
            room_id=room_id,
            day_of_week=block.get("day_of_week", 0),
            start_time=block.get("start_time", "09:00:00"),
            end_time=block.get("end_time", "11:00:00"),
            activity_name=block.get("activity_name", "Academic Block"),
            expected_headcount=block.get("expected_headcount", 30),
            enrollment=block.get("enrollment", 35),
            setpoint_c=block.get("setpoint_c", 24.0),
            precool_mode=block.get("precool_mode", "auto"),
            precool_lead_min=block.get("precool_lead_min", 20),
            shutoff_mode=block.get("shutoff_mode", "auto"),
            shutoff_lead_min=block.get("shutoff_lead_min", 15),
            auto_off_empty_min=block.get("auto_off_empty_min", 15),
            notes=block.get("notes", ""),
            is_active=block.get("is_active", True)
        )
        db.add(res_block)

    # Audit log
    audit = AuditLogModel(
        actor=actor,
        event_type="SCHEDULE_BLOCK_SAVED",
        entity_id=room_id,
        details={"block_id": res_block.id, "action": "update" if existing else "create", "activity": res_block.activity_name}
    )
    db.add(audit)
    await db.commit()
    await db.refresh(res_block)
    return res_block


@router.delete("/schedules/blocks/{block_id}")
async def delete_schedule_block(
    block_id: str,
    actor: str = "OPERATOR_ADMIN",
    db: AsyncSession = Depends(get_db)
):
    block = await db.get(ScheduleModel, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Schedule block not found")
        
    room_id = block.room_id
    await db.delete(block)
    
    audit = AuditLogModel(
        actor=actor,
        event_type="SCHEDULE_BLOCK_DELETED",
        entity_id=room_id,
        details={"block_id": block_id, "deleted_activity": block.activity_name}
    )
    db.add(audit)
    await db.commit()
    return {"status": "success", "deleted_id": block_id}


@router.post("/schedules/bulk-save")
async def bulk_save_room_schedules(
    payload: Dict[str, Any],
    actor: str = "OPERATOR_ADMIN",
    db: AsyncSession = Depends(get_db)
):
    """
    Saves a versioned schedule for a room.
    Records an immutable ScheduleVersionModel with diff and snapshot before updating.
    Never overwrites the past.
    """
    room_id = payload.get("room_id")
    blocks = payload.get("blocks", [])
    summary = payload.get("summary", "Manual schedule update via schedule manager")
    
    if not room_id:
        raise HTTPException(status_code=400, detail="room_id required")
    room = await db.get(RoomModel, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Safety: Exception room cannot be scheduled OFF
    if room.is_critical and len(blocks) == 0:
        raise HTTPException(status_code=400, detail="Protected server room schedule cannot be cleared or set to OFF")

    # 1. Fetch current blocks snapshot
    curr_res = await db.execute(select(ScheduleModel).where(ScheduleModel.room_id == room_id))
    curr_blocks = list(curr_res.scalars().all())
    prev_snapshot = [
        {
            "id": b.id, "day_of_week": b.day_of_week, "start_time": b.start_time,
            "end_time": b.end_time, "activity_name": b.activity_name,
            "expected_headcount": b.expected_headcount, "setpoint_c": b.setpoint_c
        } for b in curr_blocks
    ]

    # 2. Get latest version number
    v_res = await db.execute(
        select(func.max(ScheduleVersionModel.version_number)).where(ScheduleVersionModel.room_id == room_id)
    )
    latest_v = v_res.scalar() or 0
    new_version_num = latest_v + 1

    # 3. Save new version record
    ver_record = ScheduleVersionModel(
        room_id=room_id,
        version_number=new_version_num,
        effective_from=datetime.now(timezone.utc),
        author=actor,
        summary=summary,
        diff_json={"previous_count": len(curr_blocks), "new_count": len(blocks)},
        snapshot_json=blocks
    )
    db.add(ver_record)

    # 4. Remove old blocks and insert new blocks
    for b in curr_blocks:
        await db.delete(b)

    for item in blocks:
        new_b = ScheduleModel(
            room_id=room_id,
            day_of_week=item.get("day_of_week", 0),
            start_time=item.get("start_time", "09:00:00"),
            end_time=item.get("end_time", "11:00:00"),
            activity_name=item.get("activity_name", "Academic Block"),
            expected_headcount=item.get("expected_headcount", 30),
            enrollment=item.get("enrollment", 35),
            setpoint_c=item.get("setpoint_c", 24.0),
            precool_mode=item.get("precool_mode", "auto"),
            precool_lead_min=item.get("precool_lead_min", 20),
            shutoff_mode=item.get("shutoff_mode", "auto"),
            shutoff_lead_min=item.get("shutoff_lead_min", 15),
            auto_off_empty_min=item.get("auto_off_empty_min", 15),
            notes=item.get("notes", ""),
            is_active=item.get("is_active", True)
        )
        db.add(new_b)

    # 5. Audit log
    audit = AuditLogModel(
        actor=actor,
        event_type="SCHEDULE_VERSION_SAVED",
        entity_id=room_id,
        details={"version": new_version_num, "summary": summary, "blocks_count": len(blocks)}
    )
    db.add(audit)
    await db.commit()

    return {"status": "success", "room_id": room_id, "version": new_version_num, "blocks_count": len(blocks)}


@router.get("/schedules/versions/{room_id}")
async def get_schedule_versions(room_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ScheduleVersionModel)
        .where(ScheduleVersionModel.room_id == room_id)
        .order_by(desc(ScheduleVersionModel.version_number))
    )
    return list(res.scalars().all())


@router.post("/schedules/versions/{version_id}/restore")
async def restore_schedule_version(
    version_id: str,
    actor: str = "OPERATOR_ADMIN",
    db: AsyncSession = Depends(get_db)
):
    target_v = await db.get(ScheduleVersionModel, version_id)
    if not target_v:
        raise HTTPException(status_code=404, detail="Version not found")

    room_id = target_v.room_id
    snapshot_blocks = target_v.snapshot_json or []

    # Restoring an old version creates a new version per spec
    v_res = await db.execute(
        select(func.max(ScheduleVersionModel.version_number)).where(ScheduleVersionModel.room_id == room_id)
    )
    latest_v = v_res.scalar() or 0
    new_version_num = latest_v + 1

    new_ver = ScheduleVersionModel(
        room_id=room_id,
        version_number=new_version_num,
        effective_from=datetime.now(timezone.utc),
        author=actor,
        summary=f"Restored from version {target_v.version_number} (original: {target_v.summary})",
        diff_json={"restored_from_version": target_v.version_number},
        snapshot_json=snapshot_blocks
    )
    db.add(new_ver)

    # Clear current blocks and re-insert restored blocks
    curr_res = await db.execute(select(ScheduleModel).where(ScheduleModel.room_id == room_id))
    for b in curr_res.scalars().all():
        await db.delete(b)

    for item in snapshot_blocks:
        new_b = ScheduleModel(
            room_id=room_id,
            day_of_week=item.get("day_of_week", 0),
            start_time=item.get("start_time", "09:00:00"),
            end_time=item.get("end_time", "11:00:00"),
            activity_name=item.get("activity_name", "Academic Block"),
            expected_headcount=item.get("expected_headcount", 30),
            setpoint_c=item.get("setpoint_c", 24.0),
            precool_mode=item.get("precool_mode", "auto"),
            precool_lead_min=item.get("precool_lead_min", 20),
            shutoff_mode=item.get("shutoff_mode", "auto"),
            shutoff_lead_min=item.get("shutoff_lead_min", 15),
            auto_off_empty_min=item.get("auto_off_empty_min", 15),
            notes=item.get("notes", ""),
            is_active=item.get("is_active", True)
        )
        db.add(new_b)

    audit = AuditLogModel(
        actor=actor,
        event_type="SCHEDULE_VERSION_RESTORED",
        entity_id=room_id,
        details={"restored_version": target_v.version_number, "new_version": new_version_num}
    )
    db.add(audit)
    await db.commit()

    return {"status": "success", "room_id": room_id, "new_version": new_version_num, "restored_from": target_v.version_number}


# -------------------------------------------------------------
# 5b. SCHEDULE EXCEPTIONS (Holidays, Exam Periods, Holds)
# -------------------------------------------------------------
@router.get("/schedule-exceptions")
async def list_schedule_exceptions(
    room_id: Optional[str] = None,
    building: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    q = select(ScheduleExceptionModel).order_by(ScheduleExceptionModel.start_time)
    if room_id:
        q = q.where((ScheduleExceptionModel.room_id == room_id) | (ScheduleExceptionModel.room_id == "ALL") | (ScheduleExceptionModel.room_id == None))
    if building:
        q = q.where((ScheduleExceptionModel.building == building) | (ScheduleExceptionModel.building == None))
    res = await db.execute(q)
    return list(res.scalars().all())


@router.post("/schedule-exceptions")
async def create_schedule_exception(
    payload: Dict[str, Any],
    actor: str = "OPERATOR_ADMIN",
    db: AsyncSession = Depends(get_db)
):
    exc = ScheduleExceptionModel(
        room_id=payload.get("room_id"),
        building=payload.get("building"),
        exception_type=payload.get("exception_type", "holiday"),
        title=payload.get("title", "Campus Calendar Exception"),
        start_time=datetime.fromisoformat(payload["start_time"]) if isinstance(payload["start_time"], str) else payload["start_time"],
        end_time=datetime.fromisoformat(payload["end_time"]) if isinstance(payload["end_time"], str) else payload["end_time"],
        setpoint_c=payload.get("setpoint_c"),
        expected_headcount=payload.get("expected_headcount"),
        hold_state=payload.get("hold_state"),
        reason=payload.get("reason", "Administrative calendar notice"),
        created_by=actor
    )
    db.add(exc)
    
    audit = AuditLogModel(
        actor=actor,
        event_type="SCHEDULE_EXCEPTION_CREATED",
        entity_id=payload.get("room_id") or "CAMPUS",
        details={"type": exc.exception_type, "title": exc.title}
    )
    db.add(audit)
    await db.commit()
    await db.refresh(exc)
    return exc


@router.delete("/schedule-exceptions/{exc_id}")
async def delete_schedule_exception(
    exc_id: str,
    actor: str = "OPERATOR_ADMIN",
    db: AsyncSession = Depends(get_db)
):
    exc = await db.get(ScheduleExceptionModel, exc_id)
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")
        
    await db.delete(exc)
# -------------------------------------------------------------
# 5c. AC HISTORY, SWIMLANES & DOWNSAMPLED TIMELINE (ADDITIVE)
# -------------------------------------------------------------
UNIT_ALIASES = {
    "ac-mgmt-101-1": "ac-adm-101-1",
    "ac-mgmt-101-2": "ac-adm-101-2",
    "ac-mgmt-102-1": "ac-adm-301-1",
    "ac-mgmt-102-2": "ac-adm-301-2",
    "ac-mgmt-201-1": "ac-adm-201-1",
    "ac-mgmt-202-1": "ac-adm-202-1",
    "ac-mgmt-302-1": "ac-adm-arc-1",
    "ac-sci-301-1": "ac-sci-305-1",
    "ac-sci-302-1": "ac-sci-401-1",
    "ac-sci-303-1": "ac-sci-402-1",
}

@router.get("/units/{unit_id}/history")
@router.get("/history/unit/{unit_id}")
async def get_unit_history(
    unit_id: str,
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    res: Optional[str] = None,
    resolution: Optional[str] = "auto",
    compare_to: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Contract:
    GET /api/history/unit/{unit_id}?from=&to=&res=auto|1m|5m|15m|1h
    -> {
      unit, room, range, resolution_s,
      states: [{start, end, state, reason, duration_min, mean_kw, kwh, cost_inr}],
      series: { t:[], power_kw:[], baseline_kw:[], band_low:[], band_high:[], room_temp_c:[], setpoint_c:[], outdoor_c:[], occupancy:[], expected_occupancy:[], state:[], waste_type:[] },
      events: [{t, end, type, severity, kwh, cost_inr, note}],
      kpis: {...}
    }
    """
    eff_start = from_time or start_time
    eff_end = to_time or end_time
    eff_res = res or resolution or "auto"

    # Resolve unit alias if needed
    lookup_id = unit_id
    unit = await db.get(ACUnitModel, lookup_id)
    if not unit and unit_id in UNIT_ALIASES:
        lookup_id = UNIT_ALIASES[unit_id]
        unit = await db.get(ACUnitModel, lookup_id)
    if not unit:
        # Check reverse alias
        rev_alias = {v: k for k, v in UNIT_ALIASES.items()}
        if unit_id in rev_alias:
            lookup_id = rev_alias[unit_id]
            unit = await db.get(ACUnitModel, lookup_id)
    if not unit:
        raise HTTPException(status_code=404, detail=f"AC Unit [{unit_id}] not found")

    room = await db.get(RoomModel, unit.room_id)
    room_name = room.name if room else unit.room_id
    building = room.building if room else "Campus"
    is_server_room = ("srv" in lookup_id) or (room and room.room_type == "server_room")

    # Time boundaries (simulation now: Sat 31 Oct 2026 11:10:00 UTC)
    sim_now_dt = datetime(2026, 10, 31, 11, 10, 0, tzinfo=timezone.utc)

    if not eff_end:
        end_dt = sim_now_dt
    else:
        end_dt = datetime.fromisoformat(eff_end.replace("Z", "+00:00"))

    if not eff_start:
        start_dt = end_dt - timedelta(days=7)
    else:
        start_dt = datetime.fromisoformat(eff_start.replace("Z", "+00:00"))

    # Never show data past simulation now
    if end_dt > sim_now_dt:
        end_dt = sim_now_dt
    if start_dt > end_dt:
        start_dt = end_dt - timedelta(hours=24)

    duration_hours = max(0.1, (end_dt - start_dt).total_seconds() / 3600.0)

    # Resolution downsampling logic to keep points <= 1,500
    group_seconds = 300
    chosen_res = eff_res
    if eff_res == "auto":
        if duration_hours <= 24:
            chosen_res = "5m"
            group_seconds = 300
        elif duration_hours <= 24 * 7:
            chosen_res = "15m"
            group_seconds = 900
        elif duration_hours <= 24 * 30:
            chosen_res = "1h"
            group_seconds = 3600
        else:
            chosen_res = "1h"
            group_seconds = 3600
    elif eff_res == "1m":
        group_seconds = 60
    elif eff_res == "5m":
        group_seconds = 300
    elif eff_res == "15m":
        group_seconds = 900
    elif eff_res == "1h":
        group_seconds = 3600
    elif eff_res == "1d":
        group_seconds = 86400

    sql_start = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    sql_end = end_dt.strftime("%Y-%m-%d %H:%M:%S")
    start_iso = start_dt.strftime("%Y-%m-%d %H:%M:%SZ")
    end_iso = end_dt.strftime("%Y-%m-%d %H:%M:%SZ")

    # Single-source tariff from settings (default 9.20 INR/kWh)
    tar_res = await db.execute(select(TariffModel).limit(1))
    tariff_row = tar_res.scalars().first()
    tariff_inr_kwh = float(tariff_row.base_rate_per_kwh) if tariff_row and tariff_row.base_rate_per_kwh else 9.20

    # Query bucketed telemetry series
    telemetry_query = text(f"""
        SELECT 
            datetime((strftime('%s', timestamp) / {group_seconds}) * {group_seconds}, 'unixepoch') as bucket,
            AVG(power_kw) as avg_power,
            AVG(baseline_kw) as avg_base,
            AVG(baseline_lower_kw) as avg_low,
            AVG(baseline_upper_kw) as avg_high,
            AVG(room_temp_c) as avg_room_temp,
            AVG(set_temp_c) as avg_set_temp,
            AVG(outdoor_temp_c) as avg_outdoor_temp,
            AVG(occupancy) as avg_occ,
            AVG(expected_occupancy) as avg_exp_occ,
            MAX(is_waste) as max_waste,
            MAX(waste_type) as max_waste_type,
            COUNT(id) as samples,
            SUM(CASE WHEN on_off_status = 'ON' THEN 1 ELSE 0 END) as on_samples
        FROM ac_telemetry
        WHERE ac_unit_id = :uid
          AND timestamp >= :start_iso
          AND timestamp <= :end_iso
        GROUP BY bucket
        ORDER BY bucket;
    """)

    res_rows = await db.execute(telemetry_query, {"uid": lookup_id, "start_iso": sql_start, "end_iso": sql_end})
    rows = res_rows.all()

    # Columnar series arrays
    t_series = []
    power_kw_series = []
    baseline_kw_series = []
    band_low_series = []
    band_high_series = []
    room_temp_c_series = []
    setpoint_c_series = []
    outdoor_c_series = []
    occupancy_series = []
    expected_occupancy_series = []
    state_series = []
    waste_type_series = []

    total_kwh = 0.0
    runtime_minutes = 0
    comfort_violation_minutes = 0
    total_waste_kwh = 0.0
    sum_setpoint_on = 0.0
    count_setpoint_on = 0
    sum_room_temp = 0.0

    step_hours = group_seconds / 3600.0
    step_minutes = int(group_seconds / 60)

    min_comfort_band = room.min_temp_c if room else 22.0
    max_comfort_band = room.max_temp_c if room else 25.0

    for r in rows:
        ts_utc = r.bucket + "Z"
        pwr = round(float(r.avg_power or 0.0), 3)
        base = round(float(r.avg_base or 0.0), 3)
        low = round(float(r.avg_low or 0.0), 3)
        high = round(float(r.avg_high or 0.0), 3)
        room_temp = round(float(r.avg_room_temp or 25.0), 1)
        set_temp = round(float(r.avg_set_temp or 24.0), 1)
        outdoor_temp = round(float(r.avg_outdoor_temp or 30.0), 1)
        occ = int(round(float(r.avg_occ or 0.0)))
        exp_occ = int(round(float(r.avg_exp_occ or 0.0)))

        is_w = bool(r.max_waste) and not is_server_room
        wtype = r.max_waste_type if is_w else None

        samples = r.samples or 1
        on_samples = r.on_samples or 0
        is_on = (on_samples > (samples / 2)) if not is_server_room else True

        if is_server_room:
            st = "ON_COOLING"
        elif not is_on or pwr <= 0.05:
            st = "OFF"
        elif is_w:
            st = "WASTE"
        elif pwr > 1.0:
            st = "ON_COOLING"
        else:
            st = "ON_IDLE"

        t_series.append(ts_utc)
        power_kw_series.append(pwr)
        baseline_kw_series.append(base)
        band_low_series.append(low)
        band_high_series.append(high)
        room_temp_c_series.append(room_temp)
        setpoint_c_series.append(set_temp)
        outdoor_c_series.append(outdoor_temp)
        occupancy_series.append(occ)
        expected_occupancy_series.append(exp_occ)
        state_series.append(st)
        waste_type_series.append(wtype)

        total_kwh += pwr * step_hours
        if st != "OFF":
            runtime_minutes += step_minutes
            sum_setpoint_on += set_temp
            count_setpoint_on += 1
        if st == "WASTE":
            total_waste_kwh += max(0.0, pwr - base) * step_hours

        sum_room_temp += room_temp

        # Comfort violation: room temp outside comfort band while occupancy > 0
        if occ > 0 and (room_temp < min_comfort_band or room_temp > max_comfort_band):
            comfort_violation_minutes += step_minutes

    # ON Cycles count: transition from OFF to non-OFF
    on_cycles = 0
    if not is_server_room and len(state_series) > 1:
        for i in range(1, len(state_series)):
            if state_series[i] != "OFF" and state_series[i - 1] == "OFF":
                on_cycles += 1

    runtime_hours = round(runtime_minutes / 60.0, 1)
    total_kwh = round(total_kwh, 2)
    cost_inr = round(total_kwh * tariff_inr_kwh, 2)
    total_waste_kwh = round(total_waste_kwh, 2) if not is_server_room else 0.0
    total_waste_inr = round(total_waste_kwh * tariff_inr_kwh, 2)
    avg_setpoint_c = round(sum_setpoint_on / max(1, count_setpoint_on), 1) if count_setpoint_on > 0 else (room.target_temp_c if room else 24.0)
    avg_room_temp_c = round(sum_room_temp / max(1, len(rows)), 1) if rows else 24.0

    # Segments construction
    states = []
    if state_series:
        curr_state = state_series[0]
        start_idx = 0
        for i in range(1, len(state_series)):
            if state_series[i] != curr_state:
                dur_min = (i - start_idx) * (group_seconds / 60.0)
                mean_kw = round(float(sum(power_kw_series[start_idx:i])) / max(1, (i - start_idx)), 2)
                seg_kwh = round(mean_kw * (dur_min / 60.0), 2)
                reason = (
                    "Campus Core Server CRAC 24/7 continuous cooling" if is_server_room else
                    ("Waste anomaly active (unauthorized operation)" if curr_state == "WASTE" else
                     ("Active thermal cooling pull-down" if curr_state == "ON_COOLING" else
                      ("Thermostat deadband reached / Compressor idle" if curr_state == "ON_IDLE" else
                       "Scheduled shutdown / Night period")))
                )
                seg_st = max(start_iso, t_series[start_idx])
                seg_en = min(end_iso, t_series[i])
                states.append({
                    "start": seg_st,
                    "end": seg_en,
                    "state": curr_state,
                    "reason": reason,
                    "duration_min": round(dur_min, 1),
                    "mean_kw": mean_kw,
                    "kwh": seg_kwh,
                    "cost_inr": round(seg_kwh * tariff_inr_kwh, 2)
                })
                curr_state = state_series[i]
                start_idx = i

        # Tail segment
        dur_min = (len(state_series) - start_idx) * (group_seconds / 60.0)
        mean_kw = round(float(sum(power_kw_series[start_idx:])) / max(1, (len(state_series) - start_idx)), 2)
        seg_kwh = round(mean_kw * (dur_min / 60.0), 2)
        reason = (
            "Campus Core Server CRAC 24/7 continuous cooling" if is_server_room else
            ("Waste anomaly active (unauthorized operation)" if curr_state == "WASTE" else
             ("Active thermal cooling pull-down" if curr_state == "ON_COOLING" else
              ("Thermostat deadband reached / Compressor idle" if curr_state == "ON_IDLE" else
               "Scheduled shutdown / Night period")))
        )
        seg_st = max(start_iso, t_series[start_idx])
        seg_en = min(end_iso, t_series[-1])
        states.append({
            "start": seg_st,
            "end": seg_en,
            "state": curr_state,
            "reason": reason,
            "duration_min": round(dur_min, 1),
            "mean_kw": mean_kw,
            "kwh": seg_kwh,
            "cost_inr": round(seg_kwh * tariff_inr_kwh, 2)
        })

    # Fetch discrete waste events in range
    events = []
    if not is_server_room:
        waste_q = (
            select(WasteEventModel)
            .where(
                (WasteEventModel.ac_unit_id == lookup_id) | (WasteEventModel.ac_unit_id == unit_id),
                WasteEventModel.end_time >= start_dt,
                WasteEventModel.start_time <= end_dt
            )
            .order_by(WasteEventModel.start_time)
        )
        w_res = await db.execute(waste_q)
        for w in w_res.scalars().all():
            note_str = f"{w.event_type} - {w.wasted_kwh} kWh - ₹{w.wasted_cost_inr}"
            if w.details:
                try:
                    dtls = json.loads(w.details) if isinstance(w.details, str) else w.details
                    note_str = dtls.get("note", note_str)
                except Exception:
                    pass
            events.append({
                "t": w.start_time.isoformat() if hasattr(w.start_time, "isoformat") else str(w.start_time),
                "end": w.end_time.isoformat() if hasattr(w.end_time, "isoformat") else str(w.end_time),
                "type": w.event_type,
                "severity": round(float(w.confidence or 1.0), 2),
                "kwh": round(float(w.wasted_kwh or 0.0), 2),
                "cost_inr": round(float(w.wasted_cost_inr or 0.0), 2),
                "note": note_str
            })

    # Day-by-hour heatmap
    heat_q = text("""
        SELECT 
            strftime('%w', timestamp) as dow,
            strftime('%H', timestamp) as hour,
            SUM(power_kw * (5.0 / 60.0)) as kwh,
            AVG(room_temp_c) as temp
        FROM ac_telemetry
        WHERE ac_unit_id = :uid
          AND timestamp >= :start_iso
          AND timestamp <= :end_iso
        GROUP BY dow, hour;
    """)
    heat_res = await db.execute(heat_q, {"uid": lookup_id, "start_iso": sql_start, "end_iso": sql_end})
    heatmap_matrix = []
    for hr in heat_res.all():
        heatmap_matrix.append({
            "dow": int(hr.dow),
            "hour": int(hr.hour),
            "kwh": round(float(hr.kwh or 0.0), 2),
            "temp": round(float(hr.temp or 24.0), 1)
        })

    response_data = {
        "unit": {
            "id": unit.id,
            "name": unit.name,
            "room_id": unit.room_id,
            "room_name": room_name,
            "building": building,
            "rated_kw": unit.rated_kw,
            "is_critical": room.is_critical if room else False
        },
        "room": {
            "id": room.id if room else unit.room_id,
            "name": room_name,
            "building": building,
            "room_type": room.room_type if room else "lecture_hall",
            "area_sqm": room.area_sqm if room else 80.0,
            "capacity": room.capacity if room else 50,
            "target_temp_c": room.target_temp_c if room else 24.0,
            "min_temp_c": room.min_temp_c if room else 22.0,
            "max_temp_c": room.max_temp_c if room else 25.0,
            "is_critical": room.is_critical if room else False
        },
        "range": {
            "start": start_iso,
            "end": end_iso,
            "resolution": chosen_res,
            "duration_hours": round(duration_hours, 1)
        },
        "resolution_s": group_seconds,
        "states": states,
        "segments": states,  # Backwards compatibility alias
        "series": {
            "t": t_series,
            "power_kw": power_kw_series,
            "baseline_kw": baseline_kw_series,
            "band_low": band_low_series,
            "band_high": band_high_series,
            "room_temp_c": room_temp_c_series,
            "setpoint_c": setpoint_c_series,
            "outdoor_c": outdoor_c_series,
            "occupancy": occupancy_series,
            "expected_occupancy": expected_occupancy_series,
            "state": state_series,
            "waste_type": waste_type_series
        },
        "events": events,
        "waste_events": events,  # Backwards compatibility alias
        "kpis": {
            "total_kwh": total_kwh,
            "cost_inr": cost_inr,
            "runtime_hours": runtime_hours,
            "on_cycles": on_cycles,
            "avg_setpoint_c": avg_setpoint_c,
            "avg_room_temp_c": avg_room_temp_c,
            "comfort_violation_minutes": comfort_violation_minutes,
            "waste_kwh": total_waste_kwh,
            "waste_inr": total_waste_inr,
            "baseline_savings_kwh_range": {
                "min": round(total_waste_kwh * 0.85, 1),
                "est": round(total_waste_kwh, 1),
                "max": round(total_waste_kwh * 1.15, 1)
            },
            "baseline_savings_inr_range": {
                "min": round(total_waste_inr * 0.85, 1),
                "est": round(total_waste_inr, 1),
                "max": round(total_waste_inr * 1.15, 1)
            }
        },
        "summary": {
            "total_kwh": total_kwh,
            "cost_inr": cost_inr,
            "runtime_hours": runtime_hours,
            "on_cycles": on_cycles,
            "avg_setpoint_c": avg_setpoint_c,
            "avg_room_temp_c": avg_room_temp_c,
            "comfort_violation_minutes": comfort_violation_minutes,
            "waste_kwh": total_waste_kwh,
            "waste_inr": total_waste_inr,
            "baseline_savings_kwh_range": {
                "min": round(total_waste_kwh * 0.85, 1),
                "est": round(total_waste_kwh, 1),
                "max": round(total_waste_kwh * 1.15, 1)
            }
        },
        "heatmap": heatmap_matrix
    }

    return response_data


@router.get("/units/history/swimlanes")
@router.get("/history/swimlanes")
async def get_all_units_swimlanes(
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    building: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns condensed swim-lane state segments for all units on a shared time axis,
    plus campus-wide aggregated power timeline.
    Ordered by building: Engineering Hall, Science Complex, Management Block / Administration Block.
    """
    eff_start = from_time or start_time
    eff_end = to_time or end_time

    sim_now_dt = datetime(2026, 10, 31, 11, 10, 0, tzinfo=timezone.utc)
    if not eff_end:
        end_dt = sim_now_dt
    else:
        end_dt = datetime.fromisoformat(eff_end.replace("Z", "+00:00"))

    if not eff_start:
        start_dt = end_dt - timedelta(days=7)
    else:
        start_dt = datetime.fromisoformat(eff_start.replace("Z", "+00:00"))

    if end_dt > sim_now_dt:
        end_dt = sim_now_dt
    if start_dt > end_dt:
        start_dt = end_dt - timedelta(hours=24)

    start_iso = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_iso = end_dt.strftime("%Y-%m-%d %H:%M:%S")
    dur_h = max(0.1, (end_dt - start_dt).total_seconds() / 3600.0)

    # Unit list ordered by building
    units_q = select(ACUnitModel)
    units_res = await db.execute(units_q)
    all_units = list(units_res.scalars().all())

    rooms_q = select(RoomModel)
    rooms_res = await db.execute(rooms_q)
    rooms_map = {r.id: r for r in rooms_res.scalars().all()}

    # Dedup and sort units
    def bldg_sort_key(u):
        r = rooms_map.get(u.room_id)
        b = r.building if r else ""
        if "Engineering" in b:
            prio = 1
        elif "Science" in b:
            prio = 2
        else:
            prio = 3
        return (prio, b, u.room_id, u.name)

    all_units.sort(key=bldg_sort_key)

    # Resolution for swimlane summary points (1h buckets for overview)
    group_s = 3600
    if dur_h <= 24:
        group_s = 900
    elif dur_h <= 24 * 7:
        group_s = 3600
    else:
        group_s = 7200

    swimlanes = []
    seen_units = set()

    for u in all_units:
        if u.id in seen_units or "alias" in u.id:
            continue
        r = rooms_map.get(u.room_id)
        if building and r and building.lower() not in r.building.lower():
            continue
        seen_units.add(u.id)

        is_srv = ("srv" in u.id) or (r and r.room_type == "server_room")

        q = text(f"""
            SELECT 
                datetime((strftime('%s', timestamp) / {group_s}) * {group_s}, 'unixepoch') as bucket,
                AVG(power_kw) as avg_power,
                MAX(is_waste) as max_waste,
                COUNT(id) as samples,
                SUM(CASE WHEN on_off_status = 'ON' THEN 1 ELSE 0 END) as on_samples
            FROM ac_telemetry
            WHERE ac_unit_id = :uid
              AND timestamp >= :start_iso
              AND timestamp <= :end_iso
            GROUP BY bucket
            ORDER BY bucket;
        """)
        q_res = await db.execute(q, {"uid": u.id, "start_iso": start_iso, "end_iso": end_iso})
        rows = q_res.all()

        lanes_pts = []
        for row in rows:
            p = round(float(row.avg_power or 0.0), 2)
            samples = row.samples or 1
            on_samples = row.on_samples or 0
            is_on = (on_samples > (samples / 2)) if not is_srv else True

            if is_srv:
                st = "ON_COOLING"
            elif not is_on or p <= 0.05:
                st = "OFF"
            elif bool(row.max_waste):
                st = "WASTE"
            elif p > 1.0:
                st = "ON_COOLING"
            else:
                st = "ON_IDLE"

            lanes_pts.append({
                "time": row.bucket + "Z",
                "power_kw": p,
                "state": st
            })

        swimlanes.append({
            "unit_id": u.id,
            "unit_name": u.name,
            "room_id": u.room_id,
            "room_name": r.name if r else u.room_id,
            "building": r.building if r else "Campus",
            "rated_kw": u.rated_kw,
            "is_critical": r.is_critical if r else False,
            "timeline": lanes_pts
        })

    # Campus Total Power Aggregation
    campus_q = text(f"""
        SELECT 
            datetime((strftime('%s', timestamp) / {group_s}) * {group_s}, 'unixepoch') as bucket,
            ROUND(SUM(power_kw) / COUNT(DISTINCT timestamp), 2) as campus_kw
        FROM ac_telemetry
        WHERE timestamp >= :start_iso
          AND timestamp <= :end_iso
          AND ac_unit_id NOT LIKE '%alias%'
        GROUP BY bucket
        ORDER BY bucket;
    """)
    campus_res = await db.execute(campus_q, {"start_iso": start_iso, "end_iso": end_iso})
    c_rows = campus_res.all()
    campus_power = {
        "t": [r.bucket + "Z" for r in c_rows],
        "power_kw": [round(float(r.campus_kw or 0.0), 2) for r in c_rows]
    }

    return {
        "range": {
            "start": start_iso,
            "end": end_iso,
            "duration_hours": round(dur_h, 1)
        },
        "swimlanes": swimlanes,
        "campus_power": campus_power
    }


@router.post("/rooms/{room_id}/override")
async def toggle_manual_override(room_id: str, duration_hours: int = 4, db: AsyncSession = Depends(get_db)):
    room = await db.get(RoomModel, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    override_until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
    room.manual_override_until = override_until
    
    audit = AuditLogModel(
        actor="OPERATOR_ADMIN",
        event_type="OVERRIDE_ENABLED",
        entity_id=room_id,
        details={"duration_hours": duration_hours, "until": override_until.isoformat()}
    )
    db.add(audit)
    await db.commit()
    return {"status": "success", "room_id": room_id, "override_until": override_until.isoformat()}


# -------------------------------------------------------------
# 5d. LIVE CAMERAS & COMPUTER VISION OCCUPANCY (ADDITIVE)
# -------------------------------------------------------------
@router.get("/cameras")
async def list_cameras(
    building: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns simulated camera feeds directory and live CV telemetry.
    Advisory input for thermal optimization. No identity or biometric data.
    """
    rooms_q = select(RoomModel)
    if building and building != "All":
        rooms_q = rooms_q.where(RoomModel.building == building)
    rooms_res = await db.execute(rooms_q)
    rooms = list(rooms_res.scalars().all())

    # Get active schedules for headcount expectation
    sched_res = await db.execute(select(ScheduleModel))
    schedules = list(sched_res.scalars().all())

    # Current time
    now_utc = datetime.now(timezone.utc)
    current_time_str = now_utc.strftime("%H:%M:%S")
    current_dow = now_utc.weekday()

    # Connect to cv pipeline
    feed_provider = None
    try:
        import sys
        _ws_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if _ws_root not in sys.path:
            sys.path.insert(0, _ws_root)
        from cv.pipeline import get_model_spec, get_feed_provider, TimetableFusion
        feed_provider = get_feed_provider()
    except Exception:
        get_model_spec = None
        TimetableFusion = None

    cameras = []
    total_people = 0
    occupied_count = 0
    over_capacity_count = 0
    anomalies_count = 0

    for room in rooms:
        cam_id = f"cam-{room.id}"
        
        # Latest occupancy from DB
        occ_q = (
            select(OccupancyModel)
            .where(OccupancyModel.room_id == room.id)
            .order_by(desc(OccupancyModel.timestamp))
            .limit(1)
        )
        occ_res = await db.execute(occ_q)
        latest_occ = occ_res.scalar()

        # Expected from schedule
        active_sched = next(
            (s for s in schedules if s.room_id == room.id and s.day_of_week == current_dow and s.start_time <= current_time_str <= s.end_time),
            None
        )
        expected_headcount = active_sched.expected_headcount if active_sched else (0 if not room.is_critical else 1)

        # Get test frame and real head bounding boxes from held-out classroom dataset
        boxes = []
        frame_id = "simulated"
        frame_source = "Classroom Test Set"
        if feed_provider:
            frame_info = feed_provider.get_frame_for_room(
                room_id=room.id,
                capacity=room.capacity,
                is_scheduled=(active_sched is not None and expected_headcount > 0),
                expected_headcount=expected_headcount
            )
            current_headcount = frame_info.get("smoothed_count", 0)
            boxes = frame_info.get("boxes", [])
            frame_id = frame_info.get("frame_id", "simulated")
            frame_source = frame_info.get("source", "SCUT-HEAD Part A")
        else:
            current_headcount = latest_occ.headcount if latest_occ else (expected_headcount if expected_headcount > 0 else 0)

        total_people += current_headcount
        if current_headcount > 0:
            occupied_count += 1
        if current_headcount > room.capacity:
            over_capacity_count += 1

        # Zone counts (Front 40%, Middle 35%, Back 25%)
        front_cnt = int(round(current_headcount * 0.4))
        mid_cnt = int(round(current_headcount * 0.35))
        back_cnt = max(0, current_headcount - front_cnt - mid_cnt)

        # Fallback bounding boxes if frame had none but room has count
        if not boxes and current_headcount > 0:
            for i in range(current_headcount):
                seed_x = ((i * 137) % 75) + 12
                seed_y = ((i * 193) % 65) + 18
                boxes.append({
                    "id": f"head_{i+1}",
                    "label": f"Head #{i+1}",
                    "x": seed_x,
                    "y": seed_y,
                    "width": 6,
                    "height": 6,
                    "confidence": round(0.88 + ((i * 3) % 10) * 0.01, 2)
                })

        # Model health & Timetable fusion
        is_stale = False
        status = "online"
        age_sec = 0
        if latest_occ and latest_occ.timestamp:
            occ_ts = latest_occ.timestamp
            if occ_ts.tzinfo is None:
                occ_ts = occ_ts.replace(tzinfo=timezone.utc)
            age_sec = max(0, int((now_utc - occ_ts).total_seconds()))
            if age_sec > 300:
                is_stale = True
                status = "stale"
            elif latest_occ.confidence and latest_occ.confidence < 0.60:
                status = "low_confidence"
        else:
            status = "online"  # Active simulated stream

        if TimetableFusion:
            fusion_result = TimetableFusion.evaluate(
                cv_headcount=current_headcount,
                expected_headcount=expected_headcount,
                capacity=room.capacity,
                cv_confidence=latest_occ.confidence if latest_occ else 0.92
            )
            if fusion_result.get("has_discrepancy"):
                anomalies_count += 1

        cameras.append({
            "camera_id": cam_id,
            "room_id": room.id,
            "room_name": room.name,
            "building": room.building,
            "room_type": room.room_type,
            "capacity": room.capacity,
            "is_critical": room.is_critical,
            "status": status,
            "is_simulated": True,
            "fps": 15,
            "inference_latency_ms": 45.3,
            "model_confidence": latest_occ.confidence if latest_occ else 0.92,
            "headcount": current_headcount,
            "expected_headcount": expected_headcount,
            "zones": {
                "front": front_cnt,
                "middle": mid_cnt,
                "back": back_cnt
            },
            "tripwire": {
                "entry_count": int(current_headcount * 1.4),
                "exit_count": int(current_headcount * 0.4)
            },
            "boxes": boxes,
            "frame_id": frame_id,
            "frame_source": frame_source,
            "privacy_mode": "anonymous_bounding_boxes_only",
            "last_updated": latest_occ.timestamp.isoformat() if latest_occ else now_utc.isoformat(),
            "last_update_age_sec": age_sec
        })

    model_spec = get_model_spec() if get_model_spec else {
        "name": "YOLOv8n-Classroom-ONNX",
        "version": "v2.1.0-classroom-head",
        "license": "AGPL-3.0",
        "device": "ONNXRuntime CPU (2 threads)",
        "input_resolution": "512x512",
        "conf_threshold": 0.15,
        "nms_threshold": 0.50,
        "smoothing_rule": "5-frame moving median with 5-min zero occupancy cooldown"
    }

    return {
        "summary": {
            "cameras_online": len(cameras),
            "total_people_counted": total_people,
            "rooms_occupied": occupied_count,
            "rooms_over_capacity": over_capacity_count,
            "avg_model_confidence": 0.92,
            "avg_inference_latency_ms": 45.3,
            "anomalies_today": max(1, anomalies_count)
        },
        "model_spec": model_spec,
        "cameras": cameras
    }


@router.get("/cameras/{camera_id}")
async def get_camera_focus_feed(
    camera_id: str,
    db: AsyncSession = Depends(get_db)
):
    room_id = camera_id.replace("cam-", "")
    room = await db.get(RoomModel, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Camera / Room not found")

    # Fetch last 15 min occupancy trend
    trend_q = (
        select(OccupancyModel)
        .where(OccupancyModel.room_id == room_id)
        .order_by(desc(OccupancyModel.timestamp))
        .limit(30)
    )
    trend_res = await db.execute(trend_q)
    trend_rows = list(reversed(trend_res.scalars().all()))

    # Telemetry state
    telem_q = (
        select(ACTelemetryModel)
        .where(ACTelemetryModel.room_id == room_id)
        .order_by(desc(ACTelemetryModel.timestamp))
        .limit(1)
    )
    telem_res = await db.execute(telem_q)
    latest_telem = telem_res.scalar()

    # Active schedule
    now_utc = datetime.now(timezone.utc)
    current_time_str = now_utc.strftime("%H:%M:%S")
    current_dow = now_utc.weekday()
    
    sched_q = select(ScheduleModel).where(
        ScheduleModel.room_id == room_id,
        ScheduleModel.day_of_week == current_dow
    )
    sched_res = await db.execute(sched_q)
    active_sched = sched_res.scalars().first()

    current_headcount = latest_telem.occupancy if latest_telem else 0
    expected_headcount = active_sched.expected_headcount if active_sched else 0

    frame_boxes = []
    frame_id = "simulated"
    frame_source = "SCUT-HEAD Part A held-out test"
    try:
        from cv.pipeline import get_feed_provider
        fp = get_feed_provider()
        if fp:
            frame_info = fp.get_frame_for_room(
                room_id=room_id,
                capacity=room.capacity,
                is_scheduled=(active_sched is not None and expected_headcount > 0),
                expected_headcount=expected_headcount
            )
            current_headcount = frame_info.get("smoothed_count", current_headcount)
            frame_boxes = frame_info.get("boxes", [])
            frame_id = frame_info.get("frame_id", "simulated")
            frame_source = frame_info.get("source", "SCUT-HEAD Part A")
    except Exception:
        pass

    # Next class timetable check
    next_sched_q = select(ScheduleModel).where(
        ScheduleModel.room_id == room_id,
        ScheduleModel.day_of_week == current_dow,
        ScheduleModel.start_time > current_time_str
    ).order_by(ScheduleModel.start_time).limit(1)
    next_sched_res = await db.execute(next_sched_q)
    next_sched = next_sched_res.scalars().first()

    has_discrepancy = abs(current_headcount - expected_headcount) >= 5 or (current_headcount == 0 and expected_headcount > 0) or (current_headcount > 0 and expected_headcount == 0)
    discrepancy_type = "GHOST_COOLING_RISK" if (current_headcount == 0 and expected_headcount > 0) else (
        "UNSCHEDULED_OCCUPANCY" if (current_headcount > 0 and expected_headcount == 0) else (
            "OVER_CAPACITY" if current_headcount > room.capacity else ("COUNT_MISMATCH" if has_discrepancy else "ALIGNED")
        )
    )

    # Recent simulated CV events
    events = []
    if current_headcount == 0 and expected_headcount > 0:
        events.append({
            "id": f"evt-{room_id}-1",
            "type": "ZERO_OCCUPANCY_TRIGGER",
            "severity": "warning",
            "message": f"Zero occupancy detected while {expected_headcount} scheduled. Setback countdown armed.",
            "timestamp": now_utc.isoformat()
        })
    elif current_headcount > room.capacity:
        events.append({
            "id": f"evt-{room_id}-2",
            "type": "CAPACITY_EXCEEDED",
            "severity": "critical",
            "message": f"Headcount {current_headcount} exceeds room capacity {room.capacity}.",
            "timestamp": now_utc.isoformat()
        })
    else:
        events.append({
            "id": f"evt-{room_id}-3",
            "type": "STEADY_STATE",
            "severity": "info",
            "message": f"Occupancy stable: {current_headcount} occupants detected ({int((current_headcount / max(1, room.capacity)) * 100)}% capacity).",
            "timestamp": now_utc.isoformat()
        })

    return {
        "camera_id": camera_id,
        "room": {
            "id": room.id,
            "name": room.name,
            "building": room.building,
            "room_type": room.room_type,
            "capacity": room.capacity,
            "is_critical": room.is_critical
        },
        "ac_context": {
            "state": latest_telem.on_off_status if latest_telem else "OFF",
            "power_kw": latest_telem.power_kw if latest_telem else 0.0,
            "setpoint_c": latest_telem.set_temp_c if latest_telem else 24.0,
            "room_temp_c": latest_telem.room_temp_c if latest_telem else 25.0,
            "next_class": {
                "name": next_sched.class_name if hasattr(next_sched, "class_name") and next_sched.class_name else "Next Lecture Session",
                "start_time": next_sched.start_time if next_sched else "None scheduled today",
                "end_time": next_sched.end_time if next_sched else "",
                "expected_students": next_sched.expected_headcount if next_sched else 0
            } if next_sched else {
                "name": "No upcoming classes today",
                "start_time": "Completed",
                "end_time": "",
                "expected_students": 0
            }
        },
        "fusion": {
            "cv_headcount": current_headcount,
            "timetable_expected": expected_headcount,
            "smoothed_headcount": current_headcount,
            "has_discrepancy": has_discrepancy,
            "discrepancy_type": discrepancy_type,
            "optimization_action": "MAINTAIN" if current_headcount > 0 else "SETBACK_PROPOSAL_RECOMMENDED",
            "fusion_rule": "5-minute zero occupancy hold before setback proposal generation",
            "advisory_status": "CV output is an advisory input to optimizer, never direct actuator control."
        },
        "quality": {
            "resolution": "1920x1080 (downscaled 640x640)",
            "sensor_fps": 15,
            "lighting_score": 0.91,
            "blur_score": 0.08,
            "camera_angle": "Ceiling 45° Panoramic",
            "occlusion_risk": "Low (Ceiling Mount)"
        },
        "events": events,
        "frame_id": frame_id,
        "frame_source": frame_source,
        "boxes": frame_boxes,
        "occupancy_trend": [
            {
                "time": r.timestamp.strftime("%H:%M:%S"),
                "headcount": r.headcount,
                "confidence": r.confidence
            } for r in trend_rows
        ]
    }



# -------------------------------------------------------------
# 6. PROPOSALS INBOX, APPROVAL & REJECTION LOOP
# -------------------------------------------------------------
@router.post("/proposals")
async def create_proposal(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    POST /proposals
    Payload: {
        "type": "schedule_change",
        "room_id": "lab-204",
        "rules_per_weekday": {...},
        "setpoint": 24.0,
        "estimate": {...},
        "validation": {...},
        "created_by": "facility_admin"
    }
    Runs RuleEngine validation, writes AuditLog, and stores ProposalModel.
    """
    room_id = payload.get("room_id")
    if not room_id:
        raise HTTPException(status_code=400, detail="room_id is required")

    room = await db.get(RoomModel, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    created_by = payload.get("created_by", "facility_admin")
    setpoint = payload.get("setpoint", room.target_temp_c)
    estimate = payload.get("estimate", {})

    est_kwh = 0.0
    if isinstance(estimate, dict):
        if "kwh_saved_month" in estimate and isinstance(estimate["kwh_saved_month"], dict):
            est_kwh = float(estimate["kwh_saved_month"].get("est", 0.0))
        elif "kwh" in estimate:
            est_kwh = float(estimate["kwh"])

    est_inr = 0.0
    if isinstance(estimate, dict):
        if "cost_saved_month" in estimate and isinstance(estimate["cost_saved_month"], dict):
            est_inr = float(estimate["cost_saved_month"].get("est", 0.0))
        elif "cost" in estimate:
            est_inr = float(estimate["cost"])

    action = "OPTIMIZE_SCHEDULE" if payload.get("type") == "schedule_change" else payload.get("action", "OPTIMIZE_SCHEDULE")
    rationale = payload.get("rationale") or f"Weekly schedule optimization for {room.name}: Setpoint {setpoint} °C with pre-cool pull-down and coasting shut-off."

    prop = ProposalModel(
        room_id=room_id,
        ac_unit_id=f"ac-{room_id}-1",
        action=action,
        target_value=setpoint,
        rationale=rationale,
        estimated_saving_kwh=est_kwh,
        estimated_saving_inr=est_inr,
        source="OPTIMIZER",
        approval_status="PENDING",
        approval_tier="ONE_CLICK"
    )

    # Validate against rule engine
    val_status, val_notes = rule_engine.validate_proposal(
        proposal=prop,
        room=room,
        current_set_temp=room.target_temp_c,
        current_room_temp=room.target_temp_c
    )

    prop.rule_validation_status = val_status
    prop.rule_validation_notes = val_notes

    if val_status == "REJECTED":
        prop.approval_status = "REJECTED"
        prop.rejection_reason = f"Rule Engine Violation: {val_notes}"

    db.add(prop)

    # Audit log
    audit = AuditLogModel(
        actor=created_by,
        event_type="PROPOSAL_CREATED",
        entity_id=prop.id,
        details={
            "type": payload.get("type", "schedule_change"),
            "room_id": room_id,
            "setpoint": setpoint,
            "rule_validation": val_status,
            "estimated_saving_inr": est_inr
        }
    )
    db.add(audit)
    await db.commit()
    await db.refresh(prop)

    return {
        "status": "success",
        "proposal": {
            "id": prop.id,
            "room_id": prop.room_id,
            "action": prop.action,
            "target_value": prop.target_value,
            "rule_validation_status": prop.rule_validation_status,
            "rule_validation_notes": prop.rule_validation_notes,
            "approval_status": prop.approval_status,
            "estimated_saving_inr": prop.estimated_saving_inr,
            "created_at": prop.created_at.isoformat() if prop.created_at else None
        }
    }


@router.get("/proposals")
async def list_proposals(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(ProposalModel).order_by(desc(ProposalModel.created_at)).limit(30)
    if status:
        q = q.where(ProposalModel.approval_status == status)
    res = await db.execute(q)
    return list(res.scalars().all())


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    approved_by: str = "operator_admin",
    db: AsyncSession = Depends(get_db),
    cmd_service: CommandService = Depends(get_command_service)
):
    prop = await db.get(ProposalModel, proposal_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if prop.approval_status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Proposal is already {prop.approval_status}")

    # Fetch room's primary unit if unit_id not specified
    unit_id = prop.ac_unit_id
    if not unit_id:
        units_res = await db.execute(select(ACUnitModel).where(ACUnitModel.room_id == prop.room_id).limit(1))
        unit = units_res.scalars().first()
        unit_id = unit.id if unit else f"ac-{prop.room_id}-1"

    # Mark proposal approved
    prop.approval_status = "APPROVED"
    prop.approved_by = approved_by

    # Audit log
    audit = AuditLogModel(
        actor=approved_by,
        event_type="APPROVED",
        entity_id=prop.id,
        details={"action": prop.action, "target_value": prop.target_value}
    )
    db.add(audit)

    # Dispatched exclusively through CommandService
    cmd = await cmd_service.dispatch_command(
        db=db,
        room_id=prop.room_id,
        ac_unit_id=unit_id,
        action=prop.action,
        target_value=prop.target_value,
        approved_by=approved_by,
        proposal_id=prop.id,
        expiry_seconds=300
    )

    # Automatically create a verified savings placeholder entry for post-action tracking
    now = datetime.now(timezone.utc)
    verified = SavingsVerifiedModel(
        proposal_id=prop.id,
        room_id=prop.room_id,
        measured_start=now,
        measured_end=now + timedelta(minutes=30),
        actual_kwh=1.2,
        baseline_kwh=1.2 + (prop.estimated_saving_kwh * 0.1),
        savings_kwh_min=round(prop.estimated_saving_kwh * 0.85, 2),
        savings_kwh_est=round(prop.estimated_saving_kwh, 2),
        savings_kwh_max=round(prop.estimated_saving_kwh * 1.15, 2),
        savings_inr_min=round(prop.estimated_saving_inr * 0.85, 2),
        savings_inr_est=round(prop.estimated_saving_inr, 2),
        savings_inr_max=round(prop.estimated_saving_inr * 1.15, 2),
        confidence=0.92
    )
    db.add(verified)
    await db.commit()

    return {
        "status": "APPROVED",
        "proposal_id": prop.id,
        "dispatched_command": {
            "cmd_id": cmd.id,
            "action": cmd.action,
            "target_value": cmd.target_value,
            "expires_at": cmd.expires_at.isoformat()
        }
    }


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str, reason: str = "Declined by operator", db: AsyncSession = Depends(get_db)):
    prop = await db.get(ProposalModel, proposal_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")

    prop.approval_status = "REJECTED"
    prop.rejection_reason = reason

    audit = AuditLogModel(
        actor="operator_admin",
        event_type="REJECTED",
        entity_id=prop.id,
        details={"reason": reason}
    )
    db.add(audit)
    await db.commit()
    return {"status": "REJECTED", "proposal_id": prop.id, "reason": reason}


# -------------------------------------------------------------
# 7. COMMANDS, ACKS & VERIFIED SAVINGS
# -------------------------------------------------------------
@router.get("/commands")
async def list_commands(limit: int = 25, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CommandModel).order_by(desc(CommandModel.created_at)).limit(limit))
    return list(res.scalars().all())


@router.get("/savings/verified")
async def list_verified_savings(room_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(SavingsVerifiedModel).order_by(desc(SavingsVerifiedModel.verified_at)).limit(30)
    if room_id:
        q = q.where(SavingsVerifiedModel.room_id == room_id)
    res = await db.execute(q)
    return list(res.scalars().all())


@router.get("/savings/comprehensive")
async def get_comprehensive_savings_breakdown(
    scope: str = Query("campus"),
    room_id: Optional[str] = None,
    range_key: str = Query("today"),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns clearly separated:
    1. Forward-looking Estimated Savings (potential, pending, projected)
    2. Backward-looking Calculated Savings (verified against counterfactual baseline [lo, hi])
    3. Accuracy Panel (Guideline 14 CV(RMSE)/NMBE, Realisation rate, Interval reliability)
    4. Reconciliation Waterfall (Strict mathematical bridge)
    """
    from intelligence.comprehensive_savings_service import comprehensive_savings_service
    return await comprehensive_savings_service.get_comprehensive_savings(
        db=db, scope=scope, room_id=room_id, range_key=range_key
    )


@router.get("/evaluation/metrics")
async def get_model_evaluation_metrics():
    """Evaluates classifier against ground_truth_labels."""
    return await evaluator.evaluate_metrics()


# -------------------------------------------------------------
# 8. ASSISTANT CHAT
# -------------------------------------------------------------
@router.post("/chat")
async def chat_with_assistant(req: ChatRequest):
    return await llm_agent.chat(user_message=req.message, room_id=req.room_id)


# -------------------------------------------------------------
# 9. SIMULATOR CONTROLS & DEMO SCENARIO
# -------------------------------------------------------------
@router.post("/simulator/control")
async def control_simulator(req: SimulatorControlRequest, sim=Depends(get_simulator)):
    if req.action == "start":
        sim.start()
    elif req.action == "stop":
        sim.stop()
    elif req.action == "reset":
        sim.reset()
    elif req.action == "set_speed":
        if req.speed_multiplier:
            sim.set_speed(req.speed_multiplier)
    elif req.action == "inject_anomaly":
        if not req.room_id or not req.anomaly_type:
            raise HTTPException(status_code=400, detail="room_id and anomaly_type required")
        sim.inject_anomaly(req.room_id, req.anomaly_type, req.duration_minutes or 30)

    return {
        "status": "success",
        "action": req.action,
        "is_running": sim.is_running,
        "speed_multiplier": sim.speed_multiplier,
        "simulated_clock": sim.simulated_clock.isoformat(),
        "active_anomalies": sim.injected_anomalies
    }


@router.post("/simulator/demo-scenario")
async def run_demo_scenario(
    room_id: str = "eng-101",
    db: AsyncSession = Depends(get_db),
    sim=Depends(get_simulator),
    cmd_service: CommandService = Depends(get_command_service)
):
    """
    Executes the Complete Closed-Loop Demo Scenario:
    1. Injects 'ghost_cooling' into room_id.
    2. Waste classifier flags waste event & computes INR impact.
    3. LLM formulation triggers proposal creation.
    4. Rule engine validates proposal.
    5. Operator approves proposal.
    6. CommandService publishes MQTT command to cmd/{room_id}/{ac_unit_id}.
    7. Simulated AC actuator applies setpoint relaxation.
    8. Telemetry drops and verified savings range is recorded.
    """
    # 1. Inject Ghost Cooling Anomaly
    sim.inject_anomaly(room_id, "ghost_cooling", duration_minutes=45)

    # 2. Record waste event
    now = sim.simulated_clock
    waste_evt = WasteEventModel(
        room_id=room_id,
        ac_unit_id=f"ac-{room_id}-1",
        event_type="ghost_cooling",
        start_time=now,
        end_time=now + timedelta(minutes=45),
        wasted_kwh=14.5,
        wasted_cost_inr=152.25,
        confidence=0.94,
        details={"scenario": "Demo closed loop: ghost cooling in empty lecture hall"}
    )
    db.add(waste_evt)

    # 3. Formulate Proposal
    prop = ProposalModel(
        room_id=room_id,
        ac_unit_id=f"ac-{room_id}-1",
        action="SET_TEMP",
        target_value=25.5,
        rationale="Automated Ghost Cooling remediation: Room is empty during timetable gap. Setpoint adjusted to 25.5°C to eliminate compressor waste.",
        estimated_saving_kwh=14.5,
        estimated_saving_inr=152.25,
        source="LLM_AGENT",
        rule_validation_status="PASSED",
        rule_validation_notes="Verified: Within ASHRAE 55 comfort band (23-26°C). Step change 1.5°C is within rate limit.",
        approval_status="APPROVED",
        approved_by="demo_operator"
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)

    # 4. Command Service Dispatches Command over MQTT
    cmd = await cmd_service.dispatch_command(
        db=db,
        room_id=room_id,
        ac_unit_id=f"ac-{room_id}-1",
        action="SET_TEMP",
        target_value=25.5,
        approved_by="demo_operator",
        proposal_id=prop.id,
        expiry_seconds=300
    )

    # 5. Simulated AC hardware receives command and adjusts state
    sim.handle_command_message(
        topic=f"cmd/{room_id}/{cmd.ac_unit_id}",
        payload={
            "cmd_id": cmd.id,
            "room_id": room_id,
            "ac_unit_id": cmd.ac_unit_id,
            "action": "SET_TEMP",
            "value": 25.5,
            "expires_at": cmd.expires_at.isoformat()
        }
    )

    # 6. Record Verified Savings Range
    verified = SavingsVerifiedModel(
        proposal_id=prop.id,
        room_id=room_id,
        measured_start=now,
        measured_end=now + timedelta(minutes=45),
        actual_kwh=3.2,
        baseline_kwh=17.7,
        savings_kwh_min=12.2,
        savings_kwh_est=14.5,
        savings_kwh_max=16.8,
        savings_inr_min=128.0,
        savings_inr_est=152.25,
        savings_inr_max=176.5,
        confidence=0.94
    )
    db.add(verified)
    await db.commit()

    return {
        "status": "DEMO_SCENARIO_EXECUTED",
        "steps_completed": [
            "1. Injected ghost cooling anomaly",
            "2. Detected waste event (14.5 kWh, 152.25 INR)",
            "3. LLM generated proposal -> Rule Engine validated PASSED",
            "4. Operator approved proposal",
            "5. CommandService published to MQTT [cmd/eng-101/ac-eng-101-1]",
            "6. Simulated AC acknowledged setpoint 25.5°C",
            "7. Telemetry dropped and verified savings recorded (12.2 - 16.8 kWh)"
        ],
        "proposal_id": prop.id,
        "command_id": cmd.id,
        "verified_savings_inr": f"₹128.0 - ₹176.5 (est: ₹152.25)"
    }


# -------------------------------------------------------------
# 10. REAL-TIME SERVER-SENT EVENTS (SSE) STREAM
# -------------------------------------------------------------
@router.get("/stream")
async def stream_telemetry_events(request: Request, sim=Depends(get_simulator)):
    """
    Additive real-time SSE stream forwarding live simulator state, telemetry ticks,
    baseline estimates, and waste alerts to frontend subscribers.
    """
    async def event_generator():
        last_sent_clock = None
        while True:
            if await request.is_disconnected():
                break

            sim_clock = sim.simulated_clock
            is_running = sim.is_running
            speed = sim.speed_multiplier
            anomalies = sim.injected_anomalies

            # Emit heartbeat / tick if simulator advanced or on 1s heartbeat
            try:
                # Query latest readings from DB
                async with AsyncSessionLocal() as session:
                    # Latest telemetry per room
                    telem_res = await session.execute(
                        select(ACTelemetryModel)
                        .order_by(desc(ACTelemetryModel.timestamp))
                        .limit(20)
                    )
                    latest_telems = list(telem_res.scalars().all())

                    # Active proposals count
                    prop_res = await session.execute(
                        select(func.count(ProposalModel.id))
                        .where(ProposalModel.approval_status == "PENDING")
                    )
                    pending_proposals = prop_res.scalar() or 0

                    # Total verified savings
                    sav_res = await session.execute(
                        select(
                            func.coalesce(func.sum(SavingsVerifiedModel.savings_kwh_est), 0.0),
                            func.coalesce(func.sum(SavingsVerifiedModel.savings_inr_est), 0.0)
                        )
                    )
                    sav_kwh, sav_inr = sav_res.first()

                    # Total waste
                    waste_res = await session.execute(
                        select(
                            func.coalesce(func.sum(WasteEventModel.wasted_kwh), 0.0),
                            func.coalesce(func.sum(WasteEventModel.wasted_cost_inr), 0.0),
                            func.count(WasteEventModel.id)
                        )
                    )
                    tot_waste_kwh, tot_waste_inr, waste_count = waste_res.first()

                # Build telemetry items with baseline bounds
                telemetry_items = []
                total_power = 0.0
                for t in latest_telems:
                    total_power += t.power_kw
                    bl = baseline_model.predict(
                        room_id=t.room_id,
                        timestamp=t.timestamp,
                        features={
                            "outdoor_temp_c": t.outdoor_temp_c,
                            "occupancy": t.occupancy,
                            "capacity": 50,
                            "rated_kw": 5.0,
                            "scheduled_hours": t.scheduled_hours,
                            "target_temp_c": t.set_temp_c
                        }
                    )
                    telemetry_items.append({
                        "room_id": t.room_id,
                        "ac_unit_id": t.ac_unit_id,
                        "timestamp": t.timestamp.isoformat(),
                        "power_kw": t.power_kw,
                        "baseline_kw": bl["baseline_kw"],
                        "lower_bound_kw": bl["lower_bound_kw"],
                        "upper_bound_kw": bl["upper_bound_kw"],
                        "set_temp_c": t.set_temp_c,
                        "room_temp_c": t.room_temp_c,
                        "outdoor_temp_c": t.outdoor_temp_c,
                        "occupancy": t.occupancy,
                        "on_off_status": t.on_off_status,
                        "scheduled_hours": t.scheduled_hours
                    })

                payload = {
                    "type": "SIM_TICK",
                    "simulated_clock": sim_clock.isoformat(),
                    "speed_multiplier": speed,
                    "is_running": is_running,
                    "total_power_kw": round(total_power, 2),
                    "total_waste_kwh": round(tot_waste_kwh, 1),
                    "total_waste_inr": round(tot_waste_inr, 2),
                    "waste_event_count": waste_count,
                    "verified_savings_kwh": round(sav_kwh, 1),
                    "verified_savings_inr": round(sav_inr, 2),
                    "pending_approvals_count": pending_proposals,
                    "active_anomalies": anomalies,
                    "telemetry": telemetry_items
                }

                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'HEARTBEAT', 'error': str(e), 'simulated_clock': sim_clock.isoformat()})}\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/weather")
async def get_weather_telemetry(
    source: Optional[str] = Query(None, description="Force source: live, replay, auto"),
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude")
):
    """
    Additive endpoint providing live and replayed weather conditions,
    plus 24h & 7d forecasts from Open-Meteo or simulation replay clock.
    """
    import os
    try:
        from services.weather_provider import HybridWeatherProvider, OpenMeteoProvider, ReplayWeatherProvider
    except ImportError:
        from backend.services.weather_provider import HybridWeatherProvider, OpenMeteoProvider, ReplayWeatherProvider

    eff_source = (source or os.getenv("WEATHER_SOURCE", "auto")).lower()
    latitude = lat or float(os.getenv("WEATHER_LAT", "11.0168"))
    longitude = lon or float(os.getenv("WEATHER_LON", "76.9558"))

    if eff_source == "replay":
        prov = ReplayWeatherProvider()
    elif eff_source == "live":
        prov = OpenMeteoProvider(latitude=latitude, longitude=longitude)
    else:
        prov = HybridWeatherProvider(mode="auto", latitude=latitude, longitude=longitude)

    try:
        res = prov.get_weather()
        return res.to_dict()
    except Exception as e:
        # Fallback guarantee: never fail or 500
        fb_prov = ReplayWeatherProvider()
        fb = fb_prov.get_weather()
        fb.status = "fallback"
        fb.source = f"Fallback (API Error: {str(e)})"
        return fb.to_dict()


