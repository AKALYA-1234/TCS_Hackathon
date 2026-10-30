"""
Knowledge Pack Builder & Project Docs Provider
Generates a versioned, structured knowledge pack from the repository, schemas, and live database.
Exposes get_project_docs(topic) to answer deep technical and architectural questions.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("assistant.knowledge_pack")

KNOWLEDGE_VERSION = "2026.10-v1.4"

# Comprehensive topics for get_project_docs
DOCS_CATALOG: Dict[str, Dict[str, Any]] = {
    "architecture": {
        "title": "System Architecture & Closed-Loop Pipeline",
        "content": (
            "Frostline is a closed-loop HVAC optimization system for campus AC units. "
            "Architecture comprises 5 core tiers:\n"
            "1. Edge Telemetry: AC units and synthetic sensors emit telemetry (temp, power, status, occupancy) over MQTT.\n"
            "2. Ingestion & Event Bus: Mosquitto broker routes events to FastAPI microservices and PostgreSQL.\n"
            "3. Intelligence Tier: ML Forecaster (24h/7d/30d), Seasonal Gradient Boosting Baseline, and Waste Classifier "
            "identify waste (Ghost Cooling, After-Hours, Overcooling, Empty Setback, Parasitic).\n"
            "4. Governance & Safety: RuleEngine validates every proposal against thermal envelopes (23-26°C), rate limits (<=2°C/step), "
            "and exception rooms. CommandService requires human cryptographic/operator approval before dispatching commands.\n"
            "5. User Experience: Real-time React frontend with live SSE stream and Gemini-powered Copilot."
        )
    },
    "the_loop": {
        "title": "The 7-Step Optimization Loop",
        "content": (
            "The system operates through an unceasing 7-step optimization lifecycle:\n"
            "1. Sense: Continuously streams telemetry (power kW, room temp, set temp, headcount) every 60s.\n"
            "2. Understand: Detects anomalies, evaluates waste taxonomy, and compares load against counterfactual baselines.\n"
            "3. Propose: Analytical optimizer drafts minimal-intervention setpoint, precool, or shut-off proposals.\n"
            "4. Validate: Deterministic RuleEngine checks comfort bounds, safety invariants, rate limits, and override flags.\n"
            "5. Approve: Human operator reviews proposal in Approvals Inbox or Assistant card. One-click or tiered.\n"
            "6. Act: CommandService issues signed MQTT command to cmd/{room_id}/{ac_unit_id} with strict 300s TTL.\n"
            "7. Verify: Savings engine measures difference between pre-action counterfactual baseline and actual draw."
        )
    },
    "waste_taxonomy": {
        "title": "HVAC Waste Taxonomy & Decoy Handling",
        "content": (
            "The system classifies 5 primary waste categories:\n"
            "- After-hours (AH): AC running full load outside academic/working hours (e.g., overnight/weekends).\n"
            "- Ghost Cooling (GC): AC running actively in an empty room during normal operating hours (headcount = 0 for >20 mins).\n"
            "- Overcooling (OC): Setting temperature excessively low (<21°C) when ambient comfort requires 24°C.\n"
            "- Empty Setback (ES): Failure to relax setpoint (+2°C) when room is temporarily unoccupied.\n"
            "- Parasitic Load (PL): Continuous standby draw (>0.4 kW) when AC unit is supposed to be powered off.\n"
            "Decoy Handling: Critical server rooms (e.g. eng-server) require 24/7 continuous cooling regardless of occupancy "
            "and are NEVER classified as ghost cooling or after-hours waste."
        )
    },
    "baseline_and_savings": {
        "title": "Baseline Estimation & Savings Verification Math",
        "content": (
            "1. Counterfactual Baseline: Modeled using Seasonal Gradient Boosting Baseline trained on historical weather "
            "(outdoor temperature, humidity, solar irradiation), timetable occupancy, and building thermal mass.\n"
            "2. Verified Savings: Calculated post-actuation as: Savings_kWh = max(0, Baseline_kW - Actual_kW) * Hours.\n"
            "3. Cost Savings: Calculated per tariff block: Savings_INR = Savings_kWh * Tariff_Rate.\n"
            "4. Efficiency Formula (Useful Energy Share): Defined on the dashboard as: "
            "Efficiency = (1 - (wasted_kwh / total_kwh)) * 100. Useful energy directly delivers thermal comfort."
        )
    },
    "tariffs": {
        "title": "Electricity Tariff Structure",
        "content": (
            "The campus power tariff follows a two-tier Time-of-Day (ToD) structure:\n"
            "- Standard Tariff: ₹8.50 per kWh (06:00 to 18:00, 22:00 to 06:00 IST).\n"
            "- Peak Tariff: ₹10.50 per kWh during evening grid stress (18:00 to 22:00 IST).\n"
            "All projected savings calculate kWh according to the active tariff schedule."
        )
    },
    "models": {
        "title": "Machine Learning Models & Honest Disclosures",
        "content": (
            "1. M4 Multi-Horizon Forecaster: Predicts campus total load at 24h, 7d, and 30d horizons using target-time features "
            "and lag features >= horizon.\n"
            "2. ASHRAE Gradient Boosting Baseline: Predicts counterfactual room load without optimization interventions.\n"
            "3. Isolation Forest & Rule-based Anomaly Classifier: Detects anomalous power spikes and classification into waste taxonomy.\n"
            "4. YOLOv8n-Crowd Headcount Estimator: Edge CV model running INT8/ONNX CPU inference counting occupants without facial recognition.\n"
            "Honest Disclosure: All models were trained and validated on synthetic/augmented ASHRAE campus datasets. "
            "Model weights are packaged under ml/artifacts/."
        )
    },
    "safety_and_exceptions": {
        "title": "Safety Invariants & Exception Rooms",
        "content": (
            "1. Critical Facility Exception: 'eng-server' (Central Server Room) is strictly protected with is_critical=True. "
            "Safety rule: NEVER switch off cooling. Comfort band: 20.0°C to 24.0°C. Proposals attempting to shut off are automatically rejected.\n"
            "2. Rate Limiting: Maximum setpoint adjustment per proposal step is 2.0°C to prevent thermal shock and compressor stress.\n"
            "3. Comfort Envelopes: Standard academic rooms must maintain 23.0°C to 26.0°C during active timetable sessions.\n"
            "4. Manual Override: When an instructor or admin presses manual override, room automation pauses for N hours."
        )
    },
    "roles_and_permissions": {
        "title": "Role-Based Access Control (RBAC) & Governance",
        "content": (
            "- Viewer: Read-only data queries and status questions. CANNOT create proposals, cannot approve, cannot modify schedules.\n"
            "- Facility In-charge: Can create proposals through Assistant and approve low-risk single-room adjustments (ONE_CLICK).\n"
            "- Facility Admin (Sarah Chen): Full authority. Can approve bulk proposals, schedule exceptions, emergency shutdowns, and override settings."
        )
    },
    "assumptions_and_limits": {
        "title": "System Assumptions & Operational Limitations",
        "content": (
            "- ASSUMPTION 1: Real-world camera feeds are simulated using synthetic scene generators to maintain privacy-by-design.\n"
            "- ASSUMPTION 2: Edge compute target is an Intel i7 CPU running n_jobs=4 without GPU acceleration.\n"
            "- ASSUMPTION 3: The LLM Assistant NEVER actuates hardware directly; human approval is an unbreakable invariant.\n"
            "- ASSUMPTION 4: Per-user query rate limit is 20 requests/minute; daily token budget is 100,000 tokens."
        )
    }
}


class KnowledgePack:
    def __init__(self):
        self.version = KNOWLEDGE_VERSION
        self.generated_at = datetime.now(timezone.utc).isoformat()
        self.rooms_catalog: List[Dict[str, Any]] = []
        self._init_default_catalog()

    def _init_default_catalog(self):
        # Known campus baseline catalog
        self.rooms_catalog = [
            {"room_id": "eng-101", "name": "Advanced Computing Lab", "building": "Engineering Hall", "type": "computer_lab", "capacity": 40, "tonnage": 4.0, "is_critical": False},
            {"room_id": "eng-102", "name": "Software Engineering Lab", "building": "Engineering Hall", "type": "computer_lab", "capacity": 35, "tonnage": 3.5, "is_critical": False},
            {"room_id": "eng-server", "name": "Central Server Room", "building": "Engineering Hall", "type": "server_room", "capacity": 5, "tonnage": 6.0, "is_critical": True},
            {"room_id": "sci-201", "name": "Organic Chemistry Lab", "building": "Science Complex", "type": "lab", "capacity": 30, "tonnage": 3.0, "is_critical": False},
            {"room_id": "sci-202", "name": "Physics Demonstration Hall", "building": "Science Complex", "type": "lecture_hall", "capacity": 120, "tonnage": 8.0, "is_critical": False},
            {"room_id": "adm-301", "name": "Senate Boardroom", "building": "Administration", "type": "boardroom", "capacity": 25, "tonnage": 3.0, "is_critical": False},
            {"room_id": "adm-302", "name": "Principal Office", "building": "Administration", "type": "office", "capacity": 10, "tonnage": 2.0, "is_critical": False},
            {"room_id": "lib-401", "name": "Central Library Reading Floor", "building": "Library", "type": "library", "capacity": 150, "tonnage": 10.0, "is_critical": False}
        ]

    def get_summary_context(self) -> str:
        """Returns compact system context string suitable for injection in system instructions."""
        rooms_summary = ", ".join([f"{r['room_id']} ({r['name']}, {r['type']}{' [CRITICAL EXCEPTION]' if r['is_critical'] else ''})" for r in self.rooms_catalog])
        return (
            f"=== FROSTLINE HVAC ASSISTANT PROJECT KNOWLEDGE (Version {self.version}) ===\n"
            f"SYSTEM ROLE: Senior AC Optimization Assistant for Frostline Campus Microgrid.\n"
            f"CORE INVARIANT: You NEVER actuate or execute controls directly. You ONLY create proposals that enter the Approvals Inbox for human review.\n"
            f"EXCEPTION ROOM: eng-server (Central Server Room) is critical facility; NEVER shut off cooling (20-24°C envelope).\n"
            f"TARIFFS: Standard ₹8.50/kWh, Peak ₹10.50/kWh (18:00-22:00 IST).\n"
            f"EFFICIENCY METRIC: Useful Energy Share = 1 - (wasted_kwh / total_kwh) * 100.\n"
            f"CAMPUS ROOMS: {rooms_summary}.\n"
            f"AVAILABLE PROJECT TOPICS (via get_project_docs): {', '.join(DOCS_CATALOG.keys())}.\n"
            f"HONESTY: Cite data timestamps and tool sources. Never guess or fabricate telemetry."
        )

    def get_docs(self, topic: str) -> Dict[str, Any]:
        """Provides full documentation for a given architectural or technical topic."""
        t_clean = topic.strip().lower()
        if t_clean in DOCS_CATALOG:
            doc = DOCS_CATALOG[t_clean]
            return {
                "topic": t_clean,
                "title": doc["title"],
                "content": doc["content"],
                "version": self.version,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Fuzzy match
        for key, doc in DOCS_CATALOG.items():
            if t_clean in key or key in t_clean or any(word in doc["title"].lower() for word in t_clean.split()):
                return {
                    "topic": key,
                    "title": doc["title"],
                    "content": doc["content"],
                    "version": self.version,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

        return {
            "error": f"Topic '{topic}' not found in project documentation.",
            "available_topics": list(DOCS_CATALOG.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Singleton instance
knowledge_pack = KnowledgePack()
