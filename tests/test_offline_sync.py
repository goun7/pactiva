"""
Pactiva Çevrimdışı (Offline-First) Şantiye Senkronizasyonu Testleri (tests/test_offline_sync.py)
"""

import os
from uuid import uuid4
import pytest

from pactiva_core.database import init_db
from pactiva_core.offline_sync import (
    compute_event_chain_hash,
    process_offline_attendance_batch,
)
from pactiva_core.repository import PactivaRepository


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_offline.db")
    init_db(db_file)
    repo = PactivaRepository(db_path=db_file)
    emp = repo.create_user(national_id_hash="hash_emp_offline", phone_number_encrypted="enc_p_emp", role="employer")
    wkr = repo.create_user(national_id_hash="hash_wkr_offline", phone_number_encrypted="enc_p_wkr", role="worker")
    job = repo.create_job(emp["id"], "Tünel Kazı Projesi", "construction", 250.0, 8.0)
    shift = repo.create_shift(job["id"], wkr["id"], "2026-09-08T08:00:00Z", "2026-09-08T16:00:00Z")
    return db_file, shift["id"], wkr["id"]


def test_compute_event_chain_hash_consistency():
    h1 = compute_event_chain_hash(
        prev_hash="GENESIS_0",
        shift_id="shift_123",
        worker_id="worker_456",
        ptp_monotonic_timestamp_ns=1000000000,
        wifi_rtt_distance_meters=12.45,
        event_type="check_in",
    )
    h2 = compute_event_chain_hash(
        prev_hash="GENESIS_0",
        shift_id="shift_123",
        worker_id="worker_456",
        ptp_monotonic_timestamp_ns=1000000000,
        wifi_rtt_distance_meters=12.45,
        event_type="check_in",
    )
    assert h1 == h2
    assert len(h1) == 64


def test_offline_batch_sync_success(temp_db):
    db_file, shift_id, worker_id = temp_db

    genesis = "GENESIS_BLOCK_00000000000000000000000000000000000000000000000000000000"

    # 1. Check-in olayı
    hash_1 = compute_event_chain_hash(
        prev_hash=genesis,
        shift_id=shift_id,
        worker_id=worker_id,
        ptp_monotonic_timestamp_ns=100_000_000,
        wifi_rtt_distance_meters=25.0,
        event_type="check_in",
    )

    # 2. Periyodik liveness / yoklama probe olayı
    hash_2 = compute_event_chain_hash(
        prev_hash=hash_1,
        shift_id=shift_id,
        worker_id=worker_id,
        ptp_monotonic_timestamp_ns=200_000_000,
        wifi_rtt_distance_meters=28.5,
        event_type="check_in",
    )

    # 3. Check-out olayı
    hash_3 = compute_event_chain_hash(
        prev_hash=hash_2,
        shift_id=shift_id,
        worker_id=worker_id,
        ptp_monotonic_timestamp_ns=300_000_000,
        wifi_rtt_distance_meters=30.0,
        event_type="check_out",
    )

    batch = [
        {
            "shift_id": shift_id,
            "worker_id": worker_id,
            "ptp_monotonic_timestamp_ns": 100_000_000,
            "wifi_rtt_distance_meters": 25.0,
            "event_type": "check_in",
            "event_hash": hash_1,
        },
        {
            "shift_id": shift_id,
            "worker_id": worker_id,
            "ptp_monotonic_timestamp_ns": 200_000_000,
            "wifi_rtt_distance_meters": 28.5,
            "event_type": "check_in",
            "event_hash": hash_2,
        },
        {
            "shift_id": shift_id,
            "worker_id": worker_id,
            "ptp_monotonic_timestamp_ns": 300_000_000,
            "wifi_rtt_distance_meters": 30.0,
            "event_type": "check_out",
            "event_hash": hash_3,
        },
    ]

    res = process_offline_attendance_batch(batch, db_path=db_file)
    assert res["success"] is True
    assert res["synced_count"] == 3
    assert res["final_block_hash"] == hash_3

    repo = PactivaRepository(db_path=db_file)
    events = repo.list_shift_attendance_events(shift_id)
    assert len(events) == 3


def test_offline_chronological_inversion_rejected(temp_db):
    db_file, shift_id, worker_id = temp_db
    batch = [
        {
            "shift_id": shift_id,
            "worker_id": worker_id,
            "ptp_monotonic_timestamp_ns": 500_000_000,
            "wifi_rtt_distance_meters": 10.0,
            "event_type": "check_in",
        },
        {
            "shift_id": shift_id,
            "worker_id": worker_id,
            "ptp_monotonic_timestamp_ns": 400_000_000,  # Zaman geriye sarılmış!
            "wifi_rtt_distance_meters": 10.0,
            "event_type": "check_out",
        },
    ]
    res = process_offline_attendance_batch(batch, db_path=db_file)
    assert res["success"] is False
    assert res["error_code"] == "CHRONOLOGICAL_INVERSION"


def test_offline_geofence_breach_rejected(temp_db):
    db_file, shift_id, worker_id = temp_db
    batch = [
        {
            "shift_id": shift_id,
            "worker_id": worker_id,
            "ptp_monotonic_timestamp_ns": 100_000_000,
            "wifi_rtt_distance_meters": 750.0,  # 500m sınırı aşıldı!
            "event_type": "check_in",
        }
    ]
    res = process_offline_attendance_batch(batch, db_path=db_file)
    assert res["success"] is False
    assert res["error_code"] == "GEOFENCE_BREACH"


def test_offline_tampered_hash_chain_rejected(temp_db):
    db_file, shift_id, worker_id = temp_db
    batch = [
        {
            "shift_id": shift_id,
            "worker_id": worker_id,
            "ptp_monotonic_timestamp_ns": 100_000_000,
            "wifi_rtt_distance_meters": 15.0,
            "event_type": "check_in",
            "event_hash": "tampered_fake_hash_1234567890abcdef",
        }
    ]
    res = process_offline_attendance_batch(batch, db_path=db_file)
    assert res["success"] is False
    assert res["error_code"] == "HASH_CHAIN_TAMPERED"
