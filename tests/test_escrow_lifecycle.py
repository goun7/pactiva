"""
Pactiva Emanet Kasası Yaşam Döngüsü ve Sözleşme Kriptografik Doğrulama Testleri (tests/test_escrow_lifecycle.py)
"""

from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from pactiva_core.api import app
from pactiva_core.contracts import generate_tripartite_contract
from pactiva_core.database import init_db
from pactiva_core.repository import PactivaRepository

client = TestClient(app)


@pytest.fixture
def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_escrow_lifecycle.db")
    init_db(db_file)
    repo = PactivaRepository(db_path=db_file)
    return repo


def test_escrow_release_payout_lifecycle(temp_repo):
    emp = temp_repo.create_user(national_id_hash="emp_hash_01", phone_number_encrypted="enc_p", role="employer")
    wkr = temp_repo.create_user(national_id_hash="wkr_hash_01", phone_number_encrypted="enc_p", role="worker")
    job = temp_repo.create_job(emp["id"], "Kamera Operatörü", "film_set", Decimal("400.00"), Decimal("10.0"))
    escrow = temp_repo.create_escrow_account(
        job_id=job["id"],
        locked_amount=Decimal("4800.00"),
        platform_fee=Decimal("144.00"),
        provider_tx_ref="TX_TEST_01",
    )
    assert escrow["status"] == "locked"

    # Mesai bitti, hak edişi serbest bırak
    released = temp_repo.release_escrow_payout(
        job_id=job["id"],
        payout_amount=Decimal("3600.00"),
        withholding_tax_amount=Decimal("400.00"),
    )
    assert released["status"] == "disbursed"
    assert released["withholding_tax_reserved"] == 400.0

    updated_job = temp_repo.get_job(job["id"])
    assert updated_job["status"] == "completed"

    # Tekrar serbest bırakma denemesi hata fırlatmalı
    with pytest.raises(ValueError, match="yalnızca 'locked' hesaplar"):
        temp_repo.release_escrow_payout(job["id"], Decimal("100.00"), Decimal("10.00"))


def test_escrow_refund_lifecycle(temp_repo):
    emp = temp_repo.create_user(national_id_hash="emp_hash_02", phone_number_encrypted="enc_p", role="employer")
    job = temp_repo.create_job(emp["id"], "İskele Ustası", "construction", Decimal("350.00"), Decimal("8.0"))
    temp_repo.create_escrow_account(
        job_id=job["id"],
        locked_amount=Decimal("3360.00"),
        platform_fee=Decimal("100.80"),
        provider_tx_ref="TX_TEST_02",
    )

    refunded = temp_repo.refund_escrow(job["id"], refund_reason="Hava muhalefeti sebebiyle iptal")
    assert refunded["status"] == "refunded"

    cancelled_job = temp_repo.get_job(job["id"])
    assert cancelled_job["status"] == "cancelled"


def test_escrow_release_api_endpoint():
    repo = PactivaRepository()
    emp = repo.create_user(national_id_hash=f"emp_{str(uuid4())[:8]}", phone_number_encrypted="enc_p", role="employer")
    job = repo.create_job(emp["id"], "Drone Operatörü", "film_set", Decimal("500.00"), Decimal("8.0"))
    repo.create_escrow_account(
        job_id=job["id"],
        locked_amount=Decimal("4800.00"),
        platform_fee=Decimal("144.00"),
        provider_tx_ref="TX_API_01",
    )

    payload = {
        "job_id": job["id"],
        "payout_amount": "3600.00",
        "withholding_tax_amount": "400.00",
    }
    res = client.post("/api/v1/escrow/release", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "disbursed"
    assert len(data["audit_block_hash"]) == 64


def test_contract_verify_api_endpoint():
    # Gerçek sözleşme üret
    contract = generate_tripartite_contract(
        employer_id=str(uuid4()),
        worker_id=str(uuid4()),
        job_id=str(uuid4()),
        job_title="Görüntü Asistanı",
        base_hourly_rate=Decimal("400.00"),
        expected_hours=Decimal("8.0"),
        category="film_set",
    )

    # 1. Doğru metin ile doğrulama (Kusursuz)
    valid_payload = {
        "canonical_clauses": contract["canonical_clauses"],
        "expected_hash": contract["contract_sha256_hash"],
    }
    res_valid = client.post("/api/v1/contracts/verify", json=valid_payload)
    assert res_valid.status_code == 200
    valid_data = res_valid.json()
    assert valid_data["is_valid"] is True
    assert valid_data["statutory_compliance_status"] == "VERIFIED_COMPLIANT"

    # 2. Tahrif edilmiş metin ile doğrulama
    tampered_clauses = list(contract["canonical_clauses"])
    tampered_clauses[0] = tampered_clauses[0].replace("Pactiva", "HackerCorp")

    tampered_payload = {
        "canonical_clauses": tampered_clauses,
        "expected_hash": contract["contract_sha256_hash"],
    }
    res_tampered = client.post("/api/v1/contracts/verify", json=tampered_payload)
    assert res_tampered.status_code == 200
    tampered_data = res_tampered.json()
    assert tampered_data["is_valid"] is False
    assert tampered_data["statutory_compliance_status"] == "TAMPERED_BREACH"


def test_security_headers_and_response_time():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert "X-Response-Time-MS" in res.headers
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" in res.headers
