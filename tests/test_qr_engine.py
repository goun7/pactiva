"""
Pactiva 15-Saniyelik Kriptografik Dönen QR Motoru Testleri (tests/test_qr_engine.py)
"""

import pytest
from uuid import uuid4

from pactiva_core.qr_engine import (
    generate_rolling_qr_token,
    verify_rolling_qr_token,
    QR_VALIDITY_WINDOW_SECONDS,
)


def test_qr_token_generation_structure():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    res = generate_rolling_qr_token(job_id=job_id, shift_id=shift_id, timestamp_sec=1000)

    token = res["token"]
    assert token.startswith("PACTIVA:")
    parts = token.split(":")
    assert len(parts) == 6
    assert parts[1] == job_id
    assert parts[2] == shift_id
    assert parts[3] == str(1000 // QR_VALIDITY_WINDOW_SECONDS)
    assert res["seconds_remaining"] == 15 - (1000 % 15)


def test_qr_token_valid_verification():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    t0 = 10000

    token_data = generate_rolling_qr_token(job_id=job_id, shift_id=shift_id, timestamp_sec=t0)
    verif = verify_rolling_qr_token(
        token=token_data["token"],
        expected_job_id=job_id,
        expected_shift_id=shift_id,
        current_timestamp_sec=t0 + 5,  # 5 saniye sonra aynı pencere içinde
    )
    assert verif["is_valid"] is True


def test_qr_token_drift_tolerance():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    t0 = 10005  # pencere: 667

    token_data = generate_rolling_qr_token(job_id=job_id, shift_id=shift_id, timestamp_sec=t0)
    # 15 saniye sonra (pencere: 668) -> 1 pencere drift toleransı içinde kabul edilmeli
    verif = verify_rolling_qr_token(
        token=token_data["token"],
        expected_job_id=job_id,
        expected_shift_id=shift_id,
        current_timestamp_sec=t0 + 15,
        allowed_window_drift=1,
    )
    assert verif["is_valid"] is True


def test_qr_token_expired_rejected():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    t0 = 10000

    token_data = generate_rolling_qr_token(job_id=job_id, shift_id=shift_id, timestamp_sec=t0)
    # 45 saniye sonra (3 pencere drift) -> reddedilmeli
    verif = verify_rolling_qr_token(
        token=token_data["token"],
        expected_job_id=job_id,
        expected_shift_id=shift_id,
        current_timestamp_sec=t0 + 45,
        allowed_window_drift=1,
    )
    assert verif["is_valid"] is False
    assert verif["error_code"] == "TOKEN_EXPIRED"


def test_qr_token_replay_attack_rejected():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    t0 = 20000

    token_data = generate_rolling_qr_token(job_id=job_id, shift_id=shift_id, timestamp_sec=t0)
    # 1. Doğrulama başarılı
    verif1 = verify_rolling_qr_token(
        token=token_data["token"],
        expected_job_id=job_id,
        expected_shift_id=shift_id,
        current_timestamp_sec=t0,
    )
    assert verif1["is_valid"] is True

    # 2. Aynı token tekrar yollandığında (screenshot replay attack) reddedilmeli
    verif2 = verify_rolling_qr_token(
        token=token_data["token"],
        expected_job_id=job_id,
        expected_shift_id=shift_id,
        current_timestamp_sec=t0 + 2,
    )
    assert verif2["is_valid"] is False
    assert verif2["error_code"] == "REPLAY_DETECTED"


def test_qr_token_signature_tampering_rejected():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    token_data = generate_rolling_qr_token(job_id=job_id, shift_id=shift_id, timestamp_sec=30000)

    # İmzanın son 4 karakterini manipüle et
    tampered = token_data["token"][:-4] + "dead"
    verif = verify_rolling_qr_token(
        token=tampered,
        expected_job_id=job_id,
        expected_shift_id=shift_id,
        current_timestamp_sec=30000,
    )
    assert verif["is_valid"] is False
    assert verif["error_code"] == "SIGNATURE_MISMATCH"
