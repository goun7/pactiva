"""
Pactiva 7 Üyeli Bağımsız Tahkim ve Slashing Testleri (tests/test_arbitration.py)
"""

import os
import tempfile
import pytest
from decimal import Decimal
from uuid import uuid4

from pactiva_core.database import init_db
from pactiva_core.arbitration import (
    create_dispute,
    cast_juror_vote,
    resolve_dispute,
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_dispute_creation_and_voting(temp_db):
    shift_id = str(uuid4())
    initiator_id = str(uuid4())
    dispute = create_dispute(
        shift_id=shift_id,
        initiator_id=initiator_id,
        reason="Set ışık şefi hak ediş mesai uyuşmazlığı",
        evidence_archive_hash="evidence_sha256_package_hex",
        db_path=temp_db,
    )
    assert dispute["resolution_status"] == "pending"

    # Jüri oy kütükleme
    juror_id = str(uuid4())
    vote = cast_juror_vote(
        dispute_id=dispute["id"],
        juror_id=juror_id,
        vote_decision="worker_favor",
        vote_value=Decimal("1.0"),
        stake_amount=Decimal("100.00"),
        db_path=temp_db,
    )
    # sqrt(100) = 10.00
    assert vote["quadratic_vote_weight"] == Decimal("10.00")


def test_7_member_jury_schelling_resolution_and_slashing(temp_db):
    shift_id = str(uuid4())
    dispute = create_dispute(
        shift_id=shift_id,
        initiator_id=str(uuid4()),
        reason="Fazla mesai saat anlaşmazlığı",
        evidence_archive_hash="hash_evidence",
        db_path=temp_db,
    )

    # 6 Dürüst Jüri (+1.0 oy, 100 TL teminat), 1 Kötü Niyetli Jüri (-1.0 oy, 100 TL teminat)
    votes_data = [
        {"juror_id": f"juror_honest_{i}", "vote_value": Decimal("1.0"), "stake_amount": Decimal("100.00")}
        for i in range(6)
    ]
    votes_data.append(
        {"juror_id": "juror_malicious_7", "vote_value": Decimal("-1.0"), "stake_amount": Decimal("100.00")}
    )

    result = resolve_dispute(
        dispute_id=dispute["id"],
        votes_data=votes_data,
        consensus_threshold=Decimal("0.50"),
        slash_rate=Decimal("0.30"),
        db_path=temp_db,
    )

    assert result["resolution_status"] == "resolved_worker_favored"
    # %30 slashing: 100 * 0.30 = 30 TL kesildi
    assert result["total_penalty_slashed"] == Decimal("30.00")

    # Kötü niyetli jürinin teminatı kesilmeli
    malicious = [j for j in result["juror_results"] if j["juror_id"] == "juror_malicious_7"][0]
    assert malicious["slashed_amount"] == Decimal("30.00")
    assert malicious["is_honest"] is False

    # Dürüst jüriler ödül almalı: 30 / 6 = 5.00 TL ödül
    honest = [j for j in result["juror_results"] if j["juror_id"] == "juror_honest_0"][0]
    assert honest["reward_earned"] == Decimal("5.00")
    assert honest["is_honest"] is True
