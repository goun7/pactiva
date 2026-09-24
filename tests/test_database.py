"""
Pactiva Kalıcı Veritabanı ve Repository Testleri (tests/test_database.py)
"""

import os
import tempfile
import pytest
from decimal import Decimal
from uuid import uuid4

from pactiva_core.database import init_db, get_db
from pactiva_core.repository import PactivaRepository


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    repo = PactivaRepository(db_path=path)
    yield repo, path
    if os.path.exists(path):
        os.remove(path)


def test_db_wal_mode_and_tables(temp_db):
    repo, path = temp_db
    with get_db(path) as conn:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        table_names = [t[0] for t in tables]
        assert "users" in table_names
        assert "jobs" in table_names
        assert "escrow_accounts" in table_names
        assert "shifts" in table_names
        assert "attendance_events" in table_names
        assert "tax_invoices" in table_names


def test_user_and_job_lifecycle(temp_db):
    repo, path = temp_db
    user = repo.create_user(
        national_id_hash="hash_tc_test_12345",
        phone_number_encrypted="enc_phone_5550001",
        role="employer",
        reputation_score=98.5,
    )
    assert user["id"] is not None
    assert user["reputation_score"] == 98.5

    job = repo.create_job(
        employer_id=user["id"],
        title="Büyükçekmece Şantiye Formenliği",
        category="construction",
        base_hourly_rate=Decimal("350.00"),
        expected_hours=Decimal("8.0"),
    )
    assert job["id"] is not None
    assert job["status"] == "draft"
    assert job["is_budget_locked"] == 0

    # Emanet hesabı oluştur ve ilanı aktifleştir
    escrow = repo.create_escrow_account(
        job_id=job["id"],
        locked_amount=Decimal("3360.00"),
        platform_fee=Decimal("100.80"),
        provider_tx_ref="TX-TEST-001",
    )
    assert escrow["locked_amount"] == 3360.0
    assert escrow["status"] == "locked"

    updated_job = repo.get_job(job["id"])
    assert updated_job["is_budget_locked"] == 1
    assert updated_job["status"] == "active"


def test_attendance_and_tax_lifecycle(temp_db):
    repo, path = temp_db
    worker = repo.create_user(
        national_id_hash="worker_tc_hash_99",
        phone_number_encrypted="worker_phone_enc",
        role="worker",
    )
    shift = repo.create_shift(
        job_id=str(uuid4()),
        worker_id=worker["id"],
        scheduled_start="2026-09-08T08:00:00Z",
        scheduled_end="2026-09-08T18:00:00Z",
    )
    assert shift["status"] == "scheduled"

    # Mesai check-in
    event = repo.record_attendance_event(
        shift_id=shift["id"],
        event_type="check_in",
        wifi_rtt_distance_meters=14.2,
        liveness_verification_hash="hash_liveness_test_ok",
        ptp_monotonic_timestamp=1788879900111,
        is_verified=True,
    )
    assert event["is_verified"] == 1

    updated_shift = repo.get_shift(shift["id"])
    assert updated_shift["status"] == "checked_in"
    assert updated_shift["actual_check_in"] is not None

    # GİB e-Gider Pusulası
    invoice = repo.create_tax_invoice(
        shift_id=shift["id"],
        worker_id=worker["id"],
        gib_invoice_uuid=str(uuid4()),
        gross_amount=Decimal("3500.00"),
        withholding_tax_amount=Decimal("350.00"),
        net_payout_amount=Decimal("3150.00"),
    )
    assert invoice["gross_amount"] == 3500.0
    assert invoice["withholding_tax_amount"] == 350.0
