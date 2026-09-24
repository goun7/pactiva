"""
Pactiva API V5 Testleri (tests/test_api_v5.py)
ERP Muhasebe Dışa Aktarımı, Çevrimdışı Yoklama Toplu Senkronizasyonu ve Kriptografik Denetim Zinciri API Testleri.
"""

from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from pactiva_core.api import app
from pactiva_core.offline_sync import compute_event_chain_hash
from pactiva_core.repository import PactivaRepository

client = TestClient(app)


def test_erp_export_api_endpoints():
    repo = PactivaRepository()
    # Test verisi oluştur
    s_id = str(uuid4())
    w_id = str(uuid4())
    repo.create_tax_invoice(
        shift_id=s_id,
        worker_id=w_id,
        gib_invoice_uuid=str(uuid4()),
        gross_amount=Decimal("4000.00"),
        withholding_tax_amount=Decimal("400.00"),
        net_payout_amount=Decimal("3600.00"),
    )

    # 1. GET /api/v1/erp/export?format=json
    res_json = client.get("/api/v1/erp/export?format=json")
    assert res_json.status_code == 200
    data_json = res_json.json()
    assert data_json["format"] == "json"
    assert data_json["total_entries"] >= 1
    assert "MAHSUP_FISI" in data_json["export_payload"]

    # 2. GET /api/v1/erp/export?format=logo_xml
    res_xml = client.get("/api/v1/erp/export?format=logo_xml")
    assert res_xml.status_code == 200
    data_xml = res_xml.json()
    assert data_xml["format"] == "logo_xml"
    assert "<TRANSACTIONS>" in data_xml["export_payload"]
    assert "<GL_CODE>740.01.001</GL_CODE>" in data_xml["export_payload"]

    # 3. POST /api/v1/erp/export (sap_csv)
    res_csv = client.post(
        "/api/v1/erp/export",
        json={"format": "sap_csv", "account_cost_center": "740.01.001"},
    )
    assert res_csv.status_code == 200
    data_csv = res_csv.json()
    assert data_csv["format"] == "sap_csv"
    assert "POSTING_DATE;DOCUMENT_TYPE" in data_csv["export_payload"]

    # 4. Geçersiz format
    res_inv = client.get("/api/v1/erp/export?format=invalid_fmt")
    assert res_inv.status_code == 400


def test_offline_attendance_batch_api_endpoint():
    repo = PactivaRepository()
    emp = repo.create_user(national_id_hash=f"hash_emp_{str(uuid4())[:8]}", phone_number_encrypted="enc_p", role="employer")
    wkr = repo.create_user(national_id_hash=f"hash_wkr_{str(uuid4())[:8]}", phone_number_encrypted="enc_p", role="worker")
    job = repo.create_job(emp["id"], "Metro Şantiye Hattı", "construction", 220.0, 8.0)
    shift = repo.create_shift(job["id"], wkr["id"], "2026-09-08T08:00:00Z", "2026-09-08T16:00:00Z")

    genesis = "GENESIS_BLOCK_00000000000000000000000000000000000000000000000000000000"
    h1 = compute_event_chain_hash(
        prev_hash=genesis,
        shift_id=shift["id"],
        worker_id=wkr["id"],
        ptp_monotonic_timestamp_ns=1000,
        wifi_rtt_distance_meters=18.5,
        event_type="check_in",
    )

    payload = {
        "events": [
            {
                "shift_id": shift["id"],
                "worker_id": wkr["id"],
                "ptp_monotonic_timestamp_ns": 1000,
                "wifi_rtt_distance_meters": 18.5,
                "event_type": "check_in",
                "event_hash": h1,
            }
        ]
    }
    res = client.post("/api/v1/attendance/offline-sync", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["synced_count"] == 1
    assert data["final_block_hash"] == h1


def test_audit_ledger_record_and_verify_api_endpoints():
    # 1. POST /api/v1/audit/record
    payload = {
        "action_type": "ESCROW_LOCK_API_EVENT",
        "payload": {"amount": "15000.00", "provider": "vakifbank_escrow"},
    }
    res_rec = client.post("/api/v1/audit/record", json=payload)
    assert res_rec.status_code == 201
    rec_data = res_rec.json()
    assert rec_data["block_index"] >= 1
    assert rec_data["action_type"] == "ESCROW_LOCK_API_EVENT"
    assert rec_data["is_immutable"] is True
    assert len(rec_data["block_hash"]) == 64

    # 2. GET /api/v1/audit/verify
    res_ver = client.get("/api/v1/audit/verify")
    assert res_ver.status_code == 200
    ver_data = res_ver.json()
    assert ver_data["is_valid"] is True
    assert ver_data["total_blocks"] >= 1
    assert "tahrifat bulunmuyor" in ver_data["detail"]
