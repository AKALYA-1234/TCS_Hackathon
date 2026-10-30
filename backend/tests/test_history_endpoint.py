import pytest
from httpx import AsyncClient, ASGITransport
from services.sensor_service.main import app

@pytest.mark.anyio
async def test_history_endpoint_contract_and_sanity_guards():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch Lecture Hall (ac-eng-101-1)
        res_lec = await client.get("/api/history/unit/ac-eng-101-1?res=1h")
        assert res_lec.status_code == 200, f"Lecture hall history failed: {res_lec.text}"
        lec_data = res_lec.json()

        # Contract verification
        assert "unit" in lec_data
        assert "room" in lec_data
        assert "range" in lec_data
        assert "resolution_s" in lec_data
        assert "states" in lec_data
        assert "series" in lec_data
        assert "events" in lec_data
        assert "kpis" in lec_data

        # Series equal length
        s = lec_data["series"]
        keys = ["t", "power_kw", "baseline_kw", "band_low", "band_high", "room_temp_c", "setpoint_c", "outdoor_c", "occupancy", "expected_occupancy"]
        for k in keys:
            assert k in s, f"Missing key {k} in series"
            assert len(s[k]) == len(s["t"]), f"Series length mismatch for {k}: {len(s[k])} vs {len(s['t'])}"

        # Lecture hall sanity: OFF segments at night/weekends, ON cycles > 0 over 7 days
        states = lec_data["states"]
        assert len(states) > 0
        off_segments = [st for st in states if st["state"] == "OFF"]
        assert len(off_segments) > 0, "Lecture hall should have OFF segments at night/Sunday"
        assert lec_data["kpis"]["on_cycles"] > 0, "Lecture hall must have ON cycles > 0 over 7 days"

        # Every state segment lies inside requested range
        start_t = lec_data["range"]["start"]
        end_t = lec_data["range"]["end"]
        for st in states:
            assert st["start"] >= start_t, f"Segment start {st['start']} before range start {start_t}"
            assert st["end"] <= end_t, f"Segment end {st['end']} after range end {end_t}"

        # 2. Fetch Server Room (ac-eng-srv-1)
        res_srv = await client.get("/api/history/unit/ac-eng-srv-1?res=1h")
        assert res_srv.status_code == 200
        srv_data = res_srv.json()

        srv_states = srv_data["states"]
        srv_off_segments = [st for st in srv_states if st["state"] == "OFF"]
        assert len(srv_off_segments) == 0, f"Server room should have 0 OFF segments, got {len(srv_off_segments)}"
        assert srv_data["kpis"]["waste_kwh"] == 0.0, f"Server room must have 0 waste, got {srv_data['kpis']['waste_kwh']}"
        assert srv_data["kpis"]["on_cycles"] == 0, f"Server room must have 0 ON cycles, got {srv_data['kpis']['on_cycles']}"

        # 3. Two different units never return identical power_kw arrays
        assert lec_data["series"]["power_kw"] != srv_data["series"]["power_kw"], "Lecture hall and Server room returned identical power series!"

        # Compare with Lab unit (ac-eng-102-1)
        res_lab = await client.get("/api/history/unit/ac-eng-102-1?res=1h")
        assert res_lab.status_code == 200
        lab_data = res_lab.json()
        assert lec_data["series"]["power_kw"] != lab_data["series"]["power_kw"], "Lecture hall and Lab returned identical power series!"
