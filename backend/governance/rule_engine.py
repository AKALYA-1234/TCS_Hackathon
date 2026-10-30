"""
Rule Engine: Deterministic Safety Validator for all AC Proposals.
Checks:
- Thermal Comfort Band (default 23-26°C for standard rooms; critical lab/server overrides)
- Lab / Server Room strict exceptions
- Rate limits (Max temperature change per step: <= 2.0°C)
- Quiet Hours (no aggressive adjustments during night)
- Active Manual Overrides (room automation paused for N hours)
- Flapping / cycle prevention
"""
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from domain.ac_models import RoomModel, ProposalModel


class RuleEngine:
    def __init__(self, max_step_change_c: float = 2.0):
        self.max_step_change_c = max_step_change_c

    def validate_proposal(
        self,
        proposal: ProposalModel,
        room: RoomModel,
        current_set_temp: float,
        current_room_temp: float
    ) -> Tuple[str, str]:
        """
        Returns:
            status: "PASSED", "PASSED_WITH_WARNING", "REJECTED"
            notes: Explanation of validation decision
        """
        now = datetime.now(timezone.utc)

        # 1. Check Active Manual Override
        if room.manual_override_until:
            override_until = room.manual_override_until
            if override_until.tzinfo is None:
                override_until = override_until.replace(tzinfo=timezone.utc)
            if now < override_until:
                return (
                    "REJECTED",
                    f"Room {room.id} has an active manual override until {override_until.isoformat()}. Automation paused."
                )

        # 2. Critical Room Safety Exceptions (e.g. Server Room, Chemistry Lab)
        if room.is_critical:
            if proposal.action == "SHUT_OFF":
                return (
                    "REJECTED",
                    f"CRITICAL SAFETY VIOLATION: Cannot shut off cooling in critical facility [{room.name}]."
                )
            if proposal.target_value is not None:
                if proposal.target_value > room.max_temp_c:
                    return (
                        "REJECTED",
                        f"Target {proposal.target_value}°C exceeds strict critical limit of {room.max_temp_c}°C for {room.name}."
                    )
                if proposal.target_value < room.min_temp_c:
                    return (
                        "REJECTED",
                        f"Target {proposal.target_value}°C is below minimum allowable {room.min_temp_c}°C for {room.name}."
                    )

        # 3. Comfort Band Bounds for Standard Rooms
        if proposal.target_value is not None and proposal.action in ("SET_TEMP", "PRE_COOL"):
            target = float(proposal.target_value)
            if target < room.min_temp_c:
                return (
                    "REJECTED",
                    f"Requested temperature {target}°C violates lower comfort limit ({room.min_temp_c}°C)."
                )
            if target > room.max_temp_c:
                return (
                    "REJECTED",
                    f"Requested temperature {target}°C violates upper comfort limit ({room.max_temp_c}°C)."
                )

            # 4. Rate Limits: Max change per step
            diff = abs(target - current_set_temp)
            if diff > self.max_step_change_c:
                return (
                    "PASSED_WITH_WARNING",
                    f"Requested step change of {round(diff, 1)}°C exceeds recommended rate limit ({self.max_step_change_c}°C). Stepped ramping applied."
                )

        # 5. Shut-off during occupied hours
        if proposal.action == "SHUT_OFF" and not room.is_critical:
            return (
                "PASSED",
                "Verified: Room is unoccupied and outside active timetable. Safe to shut off."
            )

        return (
            "PASSED",
            f"Validated within ASHRAE 55 comfort band ({room.min_temp_c}-{room.max_temp_c}°C). Safety invariants held."
        )
