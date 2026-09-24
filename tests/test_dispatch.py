"""
Pactiva 10-Dakika Hızlı Yedekleme (Dispatch SLA) Testleri (tests/test_dispatch.py)
"""

from decimal import Decimal
from uuid import uuid4
import pytest

from pactiva_core.dispatch import (
    rank_emergency_standby_candidates,
    trigger_emergency_dispatch,
    RUSH_BONUS_MULTIPLIER,
)


def test_emergency_candidate_ranking():
    candidates = [
        {
            "id": "cand_far_away",
            "name": "Uzak Aday",
            "distance_km": 25.0,  # 15 km limitinin dışında
            "reputation_score": 95.0,
            "reaction_time_ms": 200.0,
            "age": 25,
            "weekly_gaming_hours": 10.0,
            "is_available": True,
        },
        {
            "id": "cand_low_rep",
            "name": "Düşük İtibarlı",
            "distance_km": 4.0,
            "reputation_score": 50.0,  # 75 tabanının altında
            "reaction_time_ms": 210.0,
            "age": 28,
            "weekly_gaming_hours": 5.0,
            "is_available": True,
        },
        {
            "id": "cand_optimal",
            "name": "Optimum Yakın ve Yetkin",
            "distance_km": 2.5,
            "reputation_score": 96.0,
            "reaction_time_ms": 205.0,
            "age": 24,
            "weekly_gaming_hours": 15.0,
            "is_available": True,
        },
        {
            "id": "cand_backup",
            "name": "İkinci Yedek",
            "distance_km": 7.0,
            "reputation_score": 88.0,
            "reaction_time_ms": 240.0,
            "age": 30,
            "weekly_gaming_hours": 2.0,
            "is_available": True,
        },
    ]

    ranked = rank_emergency_standby_candidates(candidates)
    # Uzak ve düşük itibarlı adaylar elenmeli
    assert len(ranked) == 2
    assert ranked[0]["candidate_id"] == "cand_optimal"
    assert ranked[1]["candidate_id"] == "cand_backup"
    assert ranked[0]["composite_score"] > ranked[1]["composite_score"]


def test_trigger_emergency_dispatch_success():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    base_rate = Decimal("400.00")

    pool = [
        {
            "id": "worker_1",
            "name": "Ahmet Set Ekip",
            "distance_km": 3.0,
            "reputation_score": 90.0,
            "reaction_time_ms": 220.0,
            "age": 27,
            "weekly_gaming_hours": 5.0,
            "is_available": True,
        }
    ]

    res = trigger_emergency_dispatch(job_id, shift_id, base_rate, pool)
    assert res["success"] is True
    assert res["status"] == "DISPATCH_OFFERED"
    assert res["primary_assigned_candidate"]["candidate_id"] == "worker_1"
    # %20 Prim: 400 * 1.20 = 480.00 TL
    assert res["rush_hourly_rate"] == Decimal("480.00")
    assert res["rush_premium_hourly"] == Decimal("80.00")
    assert res["sla_target_minutes"] == 10


def test_trigger_emergency_dispatch_exhausted():
    job_id = str(uuid4())
    shift_id = str(uuid4())
    base_rate = Decimal("300.00")

    # Uygun olmayan veya boş havuz
    pool = [
        {
            "id": "worker_far",
            "distance_km": 30.0,
            "reputation_score": 80.0,
            "is_available": True,
        }
    ]

    res = trigger_emergency_dispatch(job_id, shift_id, base_rate, pool)
    assert res["success"] is False
    assert res["status"] == "EXHAUSTED"


def test_trigger_emergency_dispatch_db_fallback():
    from pactiva_core.repository import PactivaRepository
    repo = PactivaRepository()
    # Test çalışanı ekle
    w = repo.create_user(national_id_hash=f"hash_dispatch_{str(uuid4())[:8]}", phone_number_encrypted="enc_p", role="worker", reputation_score=95.0)

    job_id = str(uuid4())
    shift_id = str(uuid4())
    res = trigger_emergency_dispatch(job_id, shift_id, Decimal("350.00"), available_candidates=None)
    assert res["success"] is True
    assert res["status"] == "DISPATCH_OFFERED"
    assert res["primary_assigned_candidate"] is not None
