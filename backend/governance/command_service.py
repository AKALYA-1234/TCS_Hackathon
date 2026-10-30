"""
Command Service:
The ONLY component authorized to publish to MQTT topic cmd/{room_id}/{ac_unit_id}.
Enforces:
- Unique cmd_id (UUID)
- Expiry timestamps (expires_at)
- Command status persistence in PostgreSQL
- Audit logging of dispatched commands
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from domain.ac_models import CommandModel, AuditLogModel

logger = logging.getLogger("command_service")


class CommandService:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus

    async def dispatch_command(
        self,
        db: AsyncSession,
        room_id: str,
        ac_unit_id: str,
        action: str,
        target_value: Optional[float],
        approved_by: str,
        proposal_id: Optional[str] = None,
        expiry_seconds: int = 300
    ) -> CommandModel:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expiry_seconds)

        cmd = CommandModel(
            proposal_id=proposal_id,
            room_id=room_id,
            ac_unit_id=ac_unit_id,
            action=action,
            target_value=target_value,
            approved_by=approved_by,
            created_at=now,
            expires_at=expires_at,
            status="PUBLISHED"
        )
        db.add(cmd)

        # Audit log entry
        audit = AuditLogModel(
            actor=approved_by,
            event_type="COMMAND_DISPATCHED",
            entity_id=cmd.id,
            details={
                "room_id": room_id,
                "ac_unit_id": ac_unit_id,
                "action": action,
                "target_value": target_value,
                "expires_at": expires_at.isoformat()
            }
        )
        db.add(audit)
        await db.commit()
        await db.refresh(cmd)

        # Publish strictly over MQTT
        if self.event_bus:
            payload = {
                "cmd_id": cmd.id,
                "proposal_id": proposal_id,
                "room_id": room_id,
                "ac_unit_id": ac_unit_id,
                "action": action,
                "value": target_value,
                "approved_by": approved_by,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat()
            }
            topic = f"cmd/{room_id}/{ac_unit_id}"
            self.event_bus.publish(topic, payload)
            logger.info(f"🚀 Dispatched command [{cmd.id}] to topic [{topic}]")

        return cmd
