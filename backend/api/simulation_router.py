"""
Simulation Lab API Router
Mounts additive endpoints under /api/ac/simulation:
- Presets & Scenario CRUD
- Sandboxed Run execution & Results retrieval
- SSE Playback stream
- CSV & JSON Exports
"""
import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from simulation.models import ScenarioDefinition, ScenarioRunResult
from simulation.service import simulation_service

router = APIRouter(prefix="/api/ac/simulation", tags=["simulation"])


@router.get("/presets")
async def list_presets():
    """Returns built-in standard scenario presets."""
    return simulation_service.list_presets()


@router.get("/scenarios")
async def list_scenarios():
    """Lists all saved scenarios."""
    return simulation_service.list_scenarios()


@router.post("/scenarios")
async def create_or_save_scenario(scenario: ScenarioDefinition):
    """Saves a new or existing scenario."""
    errors = simulation_service.validate_scenario(scenario)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    return simulation_service.save_scenario(scenario)


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Retrieves scenario definition by ID."""
    sc = simulation_service.get_scenario(scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return sc


@router.put("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, scenario: ScenarioDefinition):
    """Updates an existing scenario."""
    scenario.id = scenario_id
    errors = simulation_service.validate_scenario(scenario)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    return simulation_service.save_scenario(scenario)


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str):
    """Deletes a saved scenario."""
    ok = simulation_service.delete_scenario(scenario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"status": "deleted", "scenario_id": scenario_id}


@router.post("/run")
async def execute_scenario_run(scenario: ScenarioDefinition):
    """
    Executes a fully isolated, sandboxed scenario run.
    Target: 24h run across all rooms in < 15 seconds.
    """
    try:
        result = simulation_service.execute_run(scenario)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@router.get("/runs/{run_id}")
async def get_run_results(run_id: str):
    """Retrieves full run evaluation and timeline series."""
    run = simulation_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/export/{format_type}")
async def export_run(run_id: str, format_type: str, mode: str = Query("optimizer")):
    """Exports run results as CSV or JSON."""
    run = simulation_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if format_type == "csv":
        csv_data = simulation_service.export_run_csv(run_id, mode)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=frostline_run_{run_id}_{mode}.csv"}
        )
    elif format_type == "json":
        return Response(
            content=run.model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=frostline_run_{run_id}.json"}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Supported: csv, json")


@router.get("/runs/{run_id}/stream")
async def stream_run_playback(run_id: str, mode: str = Query("optimizer"), speed: float = Query(60.0)):
    """
    Streams simulated step data over SSE for interactive timeline playback.
    """
    run = simulation_service.get_run(run_id)
    if not run or mode not in run.modes:
        raise HTTPException(status_code=404, detail="Run or mode not found")

    mode_res = run.modes[mode]
    steps = mode_res.timeline_steps

    async def event_generator():
        # Delay per step inversely proportional to speed
        step_delay = max(0.01, min(0.5, (1.0 / max(1.0, speed)) * 5.0))
        for step in steps:
            data_json = step.model_dump_json()
            yield f"event: step\ndata: {data_json}\n\n"
            await asyncio.sleep(step_delay)

        yield f"event: complete\ndata: {json.dumps({'status': 'complete', 'run_id': run_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
