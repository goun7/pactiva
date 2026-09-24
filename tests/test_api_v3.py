"""
Pactiva API V3 Uçtan Uca Entegrasyon Testleri (tests/test_api_v3.py)
"""

from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from pactiva_core.api import app

client = TestClient(app)


def test_peer_attestation_api_flow():
    worker_id = str(uuid4())
    endorser_id = str(uuid4())
    job_id = str(uuid4())

    payload = {
        "worker_id": worker_id,
        "endorser_id": endorser_id,
        "job_id": job_id,
        "overlap_start_date": "2026-04-01",
        "overlap_end_date": "2026-04-28",
        "endorser_reputation_score": 100.0,
    }

    create_res = client.post("/api/v1/attestations/create", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["is_verified"] is True
    assert data["endorser_reputation_weight"] == 1.0

    get_res = client.get(f"/api/v1/attestations/{worker_id}")
    assert get_res.status_code == 200
    summary = get_res.json()
    assert summary["total_attestations_count"] >= 1


def test_peer_attestation_self_endorsement_blocked():
    same_id = str(uuid4())
    payload = {
        "worker_id": same_id,
        "endorser_id": same_id,
        "job_id": str(uuid4()),
        "overlap_start_date": "2026-04-01",
        "overlap_end_date": "2026-04-28",
    }
    res = client.post("/api/v1/attestations/create", json=payload)
    assert res.status_code == 400
    assert "Kendi kendine" in res.json()["detail"]


def test_skill_match_api_endpoint():
    payload = {
        "job_skills": ["grip", "ışık", "kamera"],
        "candidates": [
            {
                "id": str(uuid4()),
                "name": "Uzman Grip Şefi",
                "skills": ["grip", "ışık", "kamera"],
                "reputation_score": 98.0,
            },
            {
                "id": str(uuid4()),
                "name": "Farklı Meslek",
                "skills": ["muhasebe", "finans"],
                "reputation_score": 90.0,
            },
        ],
        "min_match_threshold": 0.20,
    }
    res = client.post("/api/v1/skills/match", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_candidates_evaluated"] == 2
    assert len(data["ranked_matches"]) >= 1
    assert data["ranked_matches"][0]["name"] == "Uzman Grip Şefi"


def test_dispute_creation_and_resolution_api_flow():
    shift_id = str(uuid4())
    initiator_id = str(uuid4())

    create_payload = {
        "shift_id": shift_id,
        "initiator_id": initiator_id,
        "reason": "Gece vardiyası PTP mesai ihtilafı",
        "evidence_archive_hash": "evidence_sha256_hash_mock_package",
    }
    create_res = client.post("/api/v1/arbitration/disputes/create", json=create_payload)
    assert create_res.status_code == 201
    dispute_id = create_res.json()["id"]

    # 7 Jürili Çözümleme
    resolve_payload = {
        "votes": [
            {"juror_id": f"juror_{i}", "vote_value": "1.0", "stake_amount": "200.00"}
            for i in range(6)
        ] + [
            {"juror_id": "juror_malicious", "vote_value": "-1.0", "stake_amount": "200.00"}
        ],
        "consensus_threshold": "0.50",
        "slash_rate": "0.30",
    }
    resolve_res = client.post(f"/api/v1/arbitration/disputes/{dispute_id}/resolve", json=resolve_payload)
    assert resolve_res.status_code == 200
    res_data = resolve_res.json()
    assert res_data["resolution_status"] == "resolved_worker_favored"
    # 200 * 0.30 = 60 TL ceza
    assert Decimal(str(res_data["total_penalty_slashed"])) == Decimal("60.00")


def test_liveness_check_api_endpoint():
    # Doğal insan dokunuşu
    res_human = client.post(
        "/api/v1/liveness/verify",
        json={"tap_intervals_ms": [210.0, 245.0, 230.0, 260.0, 225.0]},
    )
    assert res_human.status_code == 200
    assert res_human.json()["is_human"] is True
    assert res_human.json()["liveness_hash"] is not None

    # Bot / makro
    res_bot = client.post(
        "/api/v1/liveness/verify",
        json={"tap_intervals_ms": [50.0, 52.0, 51.0]},
    )
    assert res_bot.status_code == 200
    assert res_bot.json()["is_human"] is False
