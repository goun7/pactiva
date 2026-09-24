"""
Pactiva API V4 Testleri (tests/test_api_v4.py)
"""

from decimal import Decimal
from uuid import uuid4
import time
import pytest
from fastapi.testclient import TestClient

from pactiva_core.api import app

client = TestClient(app)


def test_contract_generate_api_endpoint():
    payload = {
        "employer_id": str(uuid4()),
        "worker_id": str(uuid4()),
        "job_id": str(uuid4()),
        "job_title": "Maslak Plato Işık Asistanı",
        "base_hourly_rate": "380.00",
        "expected_hours": "8.0",
        "category": "film_set",
    }
    res = client.post("/api/v1/contracts/generate", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["contract_id"] is not None
    assert Decimal(str(data["estimated_total_payout"])) == Decimal("3040.00")
    assert data["statutory_compliance"]["is_4857_isolated"] is True
    assert data["is_digitally_signed"] is True
    assert len(data["contract_sha256_hash"]) == 64


def test_ptp_sync_api_endpoint():
    # Normal senkron zaman
    current_ns = time.time_ns()
    payload = {
        "client_ptp_timestamp_ns": current_ns - 30_000_000,
        "estimated_network_rtt_ns": 40_000_000,
    }
    res = client.post("/api/v1/ptp/sync", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_synchronized"] is True
    assert "senkronize edildi" in data["detail"]

    # Saat kayması manipülasyonu (> 2s)
    skewed_payload = {
        "client_ptp_timestamp_ns": current_ns + 15_000_000_000,
        "estimated_network_rtt_ns": 40_000_000,
    }
    res_skew = client.post("/api/v1/ptp/sync", json=skewed_payload)
    assert res_skew.status_code == 200
    data_skew = res_skew.json()
    assert data_skew["is_synchronized"] is False
    assert data_skew["error_code"] == "EXCESSIVE_CLOCK_SKEW"
