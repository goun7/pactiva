"""
Pactiva API Genişletilmiş Uçtan Uca Testler (tests/test_api_v2.py)
"""

from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from pactiva_core.api import app

client = TestClient(app)


def test_jobs_list_and_details():
    employer_id = str(uuid4())
    create_payload = {
        "employer_id": employer_id,
        "title": "Maslak Stüdyo Kameramanı",
        "category": "film_set",
        "base_hourly_rate": "500.00",
        "expected_hours": "6.0",
        "overtime_multiplier": "1.50",
        "escrow_provider": "bank_virtual_escrow",
    }
    create_res = client.post("/api/v1/jobs/escrow-lock", json=create_payload)
    assert create_res.status_code == 201
    job_id = create_res.json()["job_id"]

    # List jobs
    list_res = client.get("/api/v1/jobs")
    assert list_res.status_code == 200
    job_ids = [j["id"] for j in list_res.json()]
    assert job_id in job_ids

    # Job details
    detail_res = client.get(f"/api/v1/jobs/{job_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["job"]["title"] == "Maslak Stüdyo Kameramanı"
    assert detail["escrow"]["status"] == "locked"


def test_rolling_qr_generate_and_verify_flow():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    worker_id = str(uuid4())

    # 1. İşveren ekranında 15 saniyelik dönen QR üretilir
    gen_payload = {
        "job_id": job_id,
        "shift_id": shift_id,
    }
    gen_res = client.post("/api/v1/attendance/qr/generate", json=gen_payload)
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    token = gen_data["token"]
    assert token.startswith("PACTIVA:")
    assert gen_data["seconds_remaining"] <= 15

    # 2. Çalışan QR'ı tarar ve Wi-Fi RTT ile onaylar
    verify_payload = {
        "token": token,
        "job_id": job_id,
        "shift_id": shift_id,
        "worker_id": worker_id,
        "wifi_rtt_telemetry": {
            "access_points_measured": 3,
            "distance_meters": 8.5,
            "accuracy_meters": 0.8,
        },
        "liveness_hash": "a" * 64,
        "client_monotonic_ptp": 1788880000000,
    }
    verify_res = client.post("/api/v1/attendance/qr/verify", json=verify_payload)
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["is_valid"] is True
    assert verify_data["is_verified"] is True
    assert verify_data["distance_verified"] is True
    assert verify_data["actual_check_in"] is not None


def test_rolling_qr_invalid_token_rejection():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    worker_id = str(uuid4())

    verify_payload = {
        "token": "PACTIVA:fake:fake:0:fake:fakesig",
        "job_id": job_id,
        "shift_id": shift_id,
        "worker_id": worker_id,
        "liveness_hash": "b" * 64,
        "client_monotonic_ptp": 1788880000100,
    }
    verify_res = client.post("/api/v1/attendance/qr/verify", json=verify_payload)
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert data["is_valid"] is False
    assert data["is_verified"] is False


def test_emergency_dispatch_api_endpoint():
    job_id = str(uuid4())
    shift_id = str(uuid4())

    payload = {
        "job_id": job_id,
        "shift_id": shift_id,
        "base_hourly_rate": "350.00",
    }
    res = client.post(f"/api/v1/jobs/{job_id}/dispatch-emergency", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "DISPATCH_OFFERED"
    assert data["primary_assigned_candidate"] is not None
    # 350 * 1.20 = 420.00 TL
    assert Decimal(str(data["rush_hourly_rate"])) == Decimal("420.00")
    assert data["sla_target_minutes"] == 10
