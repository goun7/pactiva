"""
Pactiva Çapraz Meslektaş Doğrulama Testleri (tests/test_attestation.py)
"""

import os
import tempfile
import pytest
from uuid import uuid4

from pactiva_core.database import init_db
from pactiva_core.attestation import (
    create_peer_attestation,
    get_worker_attestations,
    compute_attestation_signature,
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_create_valid_peer_attestation(temp_db):
    worker_id = str(uuid4())
    endorser_id = str(uuid4())
    job_id = str(uuid4())

    att = create_peer_attestation(
        worker_id=worker_id,
        endorser_id=endorser_id,
        job_id=job_id,
        overlap_start_date="2026-05-01",
        overlap_end_date="2026-05-30",
        endorser_reputation_score=81.0,
        db_path=temp_db,
    )

    assert att["is_verified"] is True
    # sqrt(81 / 100) = 0.9
    assert att["endorser_reputation_weight"] == 0.9
    assert len(att["signature"]) == 32

    summary = get_worker_attestations(worker_id, db_path=temp_db)
    assert summary["total_attestations_count"] == 1
    assert summary["cumulative_trust_weight"] == 0.9


def test_prevent_self_endorsement(temp_db):
    same_id = str(uuid4())
    with pytest.raises(ValueError, match="Kendi kendine referans"):
        create_peer_attestation(
            worker_id=same_id,
            endorser_id=same_id,
            job_id=str(uuid4()),
            overlap_start_date="2026-05-01",
            overlap_end_date="2026-05-30",
            db_path=temp_db,
        )


def test_prevent_chronological_inversion(temp_db):
    with pytest.raises(ValueError, match="başlangıç tarihi bitiş tarihinden sonra olamaz"):
        create_peer_attestation(
            worker_id=str(uuid4()),
            endorser_id=str(uuid4()),
            job_id=str(uuid4()),
            overlap_start_date="2026-06-01",
            overlap_end_date="2026-05-01",
            db_path=temp_db,
        )
