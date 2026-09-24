"""
Pactiva API Entegrasyon Testleri (tests/test_api.py)
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from pactiva_core.api import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["service"] == "Pactiva Core API"


def test_frontend_index_serving():
    response = client.get("/")
    assert response.status_code == 200
    assert "Pactiva" in response.text
    assert "Canlı Saha, Set & Mesai Kokpiti" in response.text



def test_job_escrow_lock():
    payload = {
        "employer_id": str(uuid4()),
        "title": "Set Işık Şefi (Gece Vardiyası)",
        "category": "film_set",
        "base_hourly_rate": "450.00",
        "expected_hours": "10.0",
        "overtime_multiplier": "1.50",
        "escrow_provider": "bank_virtual_escrow",
    }
    response = client.post("/api/v1/jobs/escrow-lock", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["is_budget_locked"] is True
    # 450 * 10 * 1.20 = 5400.00 TL
    assert Decimal(str(data["locked_amount"])) == Decimal("5400.00")
    # %3 platform fee = 162.00 TL
    assert Decimal(str(data["platform_fee"])) == Decimal("162.00")
    assert "ESC-TR-" in data["escrow_tx_ref"]


def test_attendance_check_in():
    payload = {
        "shift_id": str(uuid4()),
        "worker_id": str(uuid4()),
        "wifi_rtt_telemetry": {
            "access_points_measured": 3,
            "distance_meters": 12.5,
            "accuracy_meters": 1.2,
        },
        "liveness_hash": "a" * 64,
        "client_monotonic_ptp": 1788872391000,
    }
    response = client.post("/api/v1/attendance/check-in", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["shift_status"] == "checked_in"
    assert data["is_verified"] is True
    assert data["distance_verified"] is True


def test_attendance_check_in_out_of_bounds():
    payload = {
        "shift_id": str(uuid4()),
        "worker_id": str(uuid4()),
        "wifi_rtt_telemetry": {
            "access_points_measured": 2,
            "distance_meters": 850.0,  # 500m geofence dışı
            "accuracy_meters": 2.0,
        },
        "liveness_hash": "b" * 64,
        "client_monotonic_ptp": 1788872392000,
    }
    response = client.post("/api/v1/attendance/check-in", json=payload)
    assert response.status_code == 400
    assert "dışındadır" in response.json()["detail"]


def test_gib_invoice_generation():
    payload = {
        "shift_id": str(uuid4()),
        "worker_id": str(uuid4()),
        "net_payout": "4500.00",
        "withholding_tax_rate": "0.10",
    }
    response = client.post("/api/v1/tax/e-gider-pusulasi/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    # 4500 net -> 5000 brüt, 500 stopaj
    assert Decimal(str(data["gross_amount"])) == Decimal("5000.00")
    assert Decimal(str(data["withholding_tax_deducted"])) == Decimal("500.00")
    assert Decimal(str(data["net_payout"])) == Decimal("4500.00")
    assert data["gib_portal_signed"] is True
    assert "https://vault.pactiva.internal/invoices/" in data["pdf_archive_url"]


def test_jury_vote():
    payload = {
        "dispute_id": str(uuid4()),
        "juror_id": str(uuid4()),
        "vote_decision": "worker_favor",
        "vote_value": "1.0",
        "stake_amount": "1000.00",
    }
    response = client.post("/api/v1/arbitration/vote", json=payload)
    assert response.status_code == 200
    data = response.json()
    # sqrt(1000) = 31.62
    assert Decimal(str(data["quadratic_vote_weight"])) == Decimal("31.62")
    assert data["status"] == "recorded"
