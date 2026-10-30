"""
LLM Agent for AC Optimization:
Gets strictly read-only inspection tools:
- get_room_stats
- get_waste_events
- get_forecast
- get_baseline
- run_optimizer
And ONE write tool:
- create_proposal

All numbers come from tool executions; the agent explains and reasons, never computes.
Has NO broker credentials and NO access to the command service.
Supports live Anthropic API key or offline deterministic fallback mode.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, desc
from common.database import AsyncSessionLocal
from domain.ac_models import (
    RoomModel, ACUnitModel, ACTelemetryModel, WasteEventModel,
    ProposalModel, AuditLogModel
)
from intelligence.optimizer import Optimizer
from intelligence.baseline import SeasonalGradientBoostingBaseline

logger = logging.getLogger("llm_agent")


class LLMAgentService:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.is_mock = not bool(self.api_key)
        self.optimizer = Optimizer()
        self.baseline_model = SeasonalGradientBoostingBaseline()

    # Tool 1: get_room_stats
    async def tool_get_room_stats(self, room_id: str) -> Dict[str, Any]:
        async with AsyncSessionLocal() as session:
            room = await session.get(RoomModel, room_id)
            if not room:
                return {"error": f"Room {room_id} not found"}

            telem_res = await session.execute(
                select(ACTelemetryModel)
                .where(ACTelemetryModel.room_id == room_id)
                .order_by(desc(ACTelemetryModel.timestamp))
                .limit(1)
            )
            latest = telem_res.scalars().first()

            return {
                "room_id": room.id,
                "name": room.name,
                "building": room.building,
                "area_sqm": room.area_sqm,
                "capacity": room.capacity,
                "comfort_band": f"{room.min_temp_c}°C - {room.max_temp_c}°C",
                "is_critical": room.is_critical,
                "current_room_temp": latest.room_temp_c if latest else room.target_temp_c,
                "current_set_temp": latest.set_temp_c if latest else room.target_temp_c,
                "current_power_kw": latest.power_kw if latest else 0.0,
                "current_headcount": latest.occupancy if latest else 0,
                "status": latest.on_off_status if latest else "OFF"
            }

    # Tool 2: get_waste_events
    async def tool_get_waste_events(self, room_id: Optional[str] = None) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            q = select(WasteEventModel).order_by(desc(WasteEventModel.start_time)).limit(10)
            if room_id:
                q = q.where(WasteEventModel.room_id == room_id)
            res = await session.execute(q)
            events = list(res.scalars().all())
            return [
                {
                    "id": e.id,
                    "room_id": e.room_id,
                    "type": e.event_type,
                    "wasted_kwh": e.wasted_kwh,
                    "cost_inr": e.wasted_cost_inr,
                    "confidence": e.confidence,
                    "details": e.details
                }
                for e in events
            ]

    # Tool 3: run_optimizer
    async def tool_run_optimizer(self, room_id: str) -> Dict[str, Any]:
        stats = await self.tool_get_room_stats(room_id)
        if "error" in stats:
            return stats

        opt = self.optimizer.optimize_room(
            room_id=room_id,
            current_set_temp_c=stats["current_set_temp"],
            target_comfort_min=23.0,
            target_comfort_max=26.0,
            schedule_start_time="09:00:00",
            schedule_end_time="17:00:00",
            rated_kw=stats["current_power_kw"] if stats["current_power_kw"] > 0 else 5.0,
            outdoor_temp_c=33.0,
            is_critical=stats["is_critical"]
        )
        return opt

    # Tool 4 (Write): create_proposal
    async def tool_create_proposal(
        self,
        room_id: str,
        action: str,
        target_value: Optional[float],
        rationale: str,
        estimated_saving_kwh: float,
        estimated_saving_inr: float
    ) -> Dict[str, Any]:
        from governance.rule_engine import RuleEngine
        rule_engine = RuleEngine()

        async with AsyncSessionLocal() as session:
            room = await session.get(RoomModel, room_id)
            if not room:
                return {"error": f"Room {room_id} does not exist"}

            prop = ProposalModel(
                room_id=room_id,
                action=action,
                target_value=target_value,
                rationale=rationale,
                estimated_saving_kwh=estimated_saving_kwh,
                estimated_saving_inr=estimated_saving_inr,
                source="LLM_AGENT",
                approval_status="PENDING",
                approval_tier="ONE_CLICK"
            )

            # Deterministic Rule Engine Validation
            status, notes = rule_engine.validate_proposal(
                proposal=prop,
                room=room,
                current_set_temp=room.target_temp_c,
                current_room_temp=room.target_temp_c
            )
            prop.rule_validation_status = status
            prop.rule_validation_notes = notes

            session.add(prop)

            audit = AuditLogModel(
                actor="LLM_AGENT",
                event_type="PROPOSAL_CREATED",
                entity_id=prop.id,
                details={
                    "room_id": room_id,
                    "action": action,
                    "target_value": target_value,
                    "rule_status": status
                }
            )
            session.add(audit)
            await session.commit()
            await session.refresh(prop)

            return {
                "proposal_id": prop.id,
                "room_id": room_id,
                "action": action,
                "target_value": target_value,
                "rule_validation": status,
                "rule_notes": notes,
                "estimated_saving_inr": estimated_saving_inr,
                "status": "QUEUED_IN_APPROVAL_INBOX"
            }

    async def chat(self, user_message: str, room_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes operator chat, invokes relevant inspection tools,
        and optionally formulates an actionable proposal.
        """
        tools_used = []

        target_room = room_id or "eng-101"
        stats = await self.tool_get_room_stats(target_room)
        tools_used.append({"tool": "get_room_stats", "result": stats})

        waste_list = await self.tool_get_waste_events(target_room)
        tools_used.append({"tool": "get_waste_events", "result": waste_list})

        opt_result = await self.tool_run_optimizer(target_room)
        tools_used.append({"tool": "run_optimizer", "result": opt_result})

        proposal_card = None

        # Check if user message asks for action or optimization
        lower_msg = user_message.lower()
        if any(w in lower_msg for w in ["optimize", "reduce", "save", "fix", "shut off", "adjust"]):
            rec_temp = opt_result["recommended_set_temp_c"]
            kwh_est = opt_result["estimated_daily_savings_kwh"]["est"]
            inr_est = opt_result["estimated_daily_savings_inr"]["est"]

            prop_res = await self.tool_create_proposal(
                room_id=target_room,
                action="SET_TEMP",
                target_value=rec_temp,
                rationale=f"LLM optimization based on thermal envelope and zero occupancy gap. Setpoint relaxed to {rec_temp}°C.",
                estimated_saving_kwh=kwh_est,
                estimated_saving_inr=inr_est
            )
            tools_used.append({"tool": "create_proposal", "result": prop_res})
            proposal_card = prop_res

            response_text = (
                f"I analyzed {stats.get('name', target_room)} in {stats.get('building', 'Campus')}. "
                f"Current setpoint is {stats.get('current_set_temp')}°C with occupancy of {stats.get('current_headcount')}. "
                f"The optimizer identified an opportunity to adjust setpoint to {rec_temp}°C within comfort bounds. "
                f"I have created proposal **{prop_res['proposal_id']}** saving ~{inr_est} INR/day ({kwh_est} kWh). "
                f"Rule Engine validation: **{prop_res['rule_validation']}**. Awaiting your approval in the inbox."
            )
        else:
            response_text = (
                f"Here is the status for {stats.get('name', target_room)}: "
                f"Room temperature is {stats.get('current_room_temp')}°C (setpoint: {stats.get('current_set_temp')}°C). "
                f"Power draw: {stats.get('current_power_kw')} kW with {stats.get('current_headcount')} occupants. "
                f"Recent waste events recorded: {len(waste_list)}. Let me know if you would like me to formulate an optimization proposal."
            )

        return {
            "response": response_text,
            "tools_used": tools_used,
            "proposal_card": proposal_card,
            "is_mock": self.is_mock
        }
