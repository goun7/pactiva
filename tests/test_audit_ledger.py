"""
Pactiva Kriptografik Denetim Zinciri (Proof-of-Audit) Testleri (tests/test_audit_ledger.py)
"""

import pytest

from pactiva_core.audit_ledger import (
    record_audit_event,
    verify_audit_ledger_integrity,
    GENESIS_PREV_HASH,
)
from pactiva_core.database import get_db, init_db


@pytest.fixture
def temp_audit_db(tmp_path):
    db_file = str(tmp_path / "test_audit.db")
    init_db(db_file)
    return db_file


def test_empty_audit_ledger_is_valid(temp_audit_db):
    res = verify_audit_ledger_integrity(db_path=temp_audit_db)
    assert res["is_valid"] is True
    assert res["total_blocks"] == 0
    assert res["latest_block_hash"] is None


def test_sequential_audit_blocks_integrity(temp_audit_db):
    # 1. Emanet kilitleme bloğu
    b1 = record_audit_event(
        action_type="ESCROW_LOCKED",
        payload={"job_id": "job_01", "locked_amount": "5000.00"},
        db_path=temp_audit_db,
    )
    assert b1["block_index"] == 1
    assert b1["prev_block_hash"] == GENESIS_PREV_HASH

    # 2. Sözleşme imzalama bloğu
    b2 = record_audit_event(
        action_type="CONTRACT_SIGNED",
        payload={"contract_id": "cnt_01", "worker_id": "wkr_01"},
        db_path=temp_audit_db,
    )
    assert b2["block_index"] == 2
    assert b2["prev_block_hash"] == b1["block_hash"]

    # 3. Stopaj ve hak ediş ödeme bloğu
    b3 = record_audit_event(
        action_type="PAYOUT_RELEASED",
        payload={"shift_id": "shf_01", "net_payout": "4500.00", "tax": "500.00"},
        db_path=temp_audit_db,
    )
    assert b3["block_index"] == 3
    assert b3["prev_block_hash"] == b2["block_hash"]

    # Zincir doğrulaması
    verify_res = verify_audit_ledger_integrity(db_path=temp_audit_db)
    assert verify_res["is_valid"] is True
    assert verify_res["total_blocks"] == 3
    assert verify_res["latest_block_hash"] == b3["block_hash"]


def test_audit_payload_tampering_detected(temp_audit_db):
    b1 = record_audit_event("ESCROW_LOCKED", {"amount": "1000.00"}, db_path=temp_audit_db)
    b2 = record_audit_event("PAYOUT_RELEASED", {"amount": "900.00"}, db_path=temp_audit_db)

    # Veritabanında gizlice payload_json tahrifatı yap
    with get_db(temp_audit_db) as conn:
        conn.execute(
            "UPDATE audit_blocks SET payload_json = ? WHERE block_index = 2",
            ('{"amount": "999999.00"}',),
        )

    verify_res = verify_audit_ledger_integrity(db_path=temp_audit_db)
    assert verify_res["is_valid"] is False
    assert verify_res["compromised_block_index"] == 2
    assert verify_res["error_code"] == "PAYLOAD_TAMPERED"


def test_audit_chain_discontinuity_detected(temp_audit_db):
    record_audit_event("BLOCK_1", {"k": 1}, db_path=temp_audit_db)
    record_audit_event("BLOCK_2", {"k": 2}, db_path=temp_audit_db)
    record_audit_event("BLOCK_3", {"k": 3}, db_path=temp_audit_db)

    # Blok #2'yi silerek zinciri kopar
    with get_db(temp_audit_db) as conn:
        conn.execute("DELETE FROM audit_blocks WHERE block_index = 2")

    verify_res = verify_audit_ledger_integrity(db_path=temp_audit_db)
    assert verify_res["is_valid"] is False
    assert verify_res["error_code"] in ("CHAIN_DISCONTINUITY", "BLOCK_HASH_INVALID")
