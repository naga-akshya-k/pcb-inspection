import pytest
from fastapi.testclient import TestClient
from server.main import app
from server.pipeline.session_manager import session_manager, PCBInspectionSession

client = TestClient(app)

def test_session_manager_basics():
    active = session_manager.get_active_session()
    assert active is not None
    assert active.pcb_id.startswith("PCB-")
    
    new_id = session_manager.generate_pcb_id()
    assert new_id.startswith("PCB-")
    assert int(new_id.split("-")[1]) > int(active.pcb_id.split("-")[1])

def test_session_endpoints():
    # 1. Get Active Session
    resp = client.get("/api/session/active")
    assert resp.status_code == 200
    data = resp.json()
    assert "pcb_id" in data
    assert "serial_number" in data
    assert "ai_verdict" in data
    
    # 2. Get History
    resp_hist = client.get("/api/sessions/history")
    assert resp_hist.status_code == 200
    hist = resp_hist.json()
    assert isinstance(hist, list)
    assert len(hist) >= 1
    
    # 3. Human Review
    rev_payload = {
        "pcb_id": data["pcb_id"],
        "decision": "ACCEPT_OVERRIDE",
        "comment": "Verified acceptable under IPC Class 2 commercial waiver.",
        "operator_id": "OP-TESTER"
    }
    resp_rev = client.post("/api/session/human-review", json=rev_payload)
    assert resp_rev.status_code == 200
    rev_data = resp_rev.json()["session"]
    assert rev_data["human_review"]["adjudicated"] is True
    assert rev_data["human_review"]["operator_decision"] == "ACCEPT_OVERRIDE"
    assert rev_data["final_verdict"] == "PASS"

def test_session_select_endpoint():
    active = session_manager.get_active_session()
    resp = client.post(f"/api/session/select/{active.pcb_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
