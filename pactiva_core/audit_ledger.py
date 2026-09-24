"""
Pactiva — Kriptografik Denetim Zinciri Motoru (pactiva_core/audit_ledger.py)
Tüm emanet, mesai ve vergi olaylarını değiştirilemez Merkle-hash zincirinde (Proof-of-Audit) mühürler.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pactiva_core.database import get_db

GENESIS_PREV_HASH: str = "0000000000000000000000000000000000000000000000000000000000000000"


def compute_block_hash(
    block_index: int,
    created_at: str,
    action_type: str,
    payload_hash: str,
    prev_block_hash: str,
) -> str:
    """Tek bir denetim bloğunun kriptografik özetini hesaplar."""
    raw = f"{block_index}:{created_at}:{action_type}:{payload_hash}:{prev_block_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_audit_event(
    action_type: str,
    payload: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sistemdeki kritik bir işlemi (emanet kilitleme, ödeme, uyuşmazlık çözümü) denetim zincirine ekler.
    """
    now = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    with get_db(db_path) as conn:
        latest = conn.execute(
            "SELECT block_index, block_hash FROM audit_blocks ORDER BY block_index DESC LIMIT 1"
        ).fetchone()

        if latest:
            next_index = latest["block_index"] + 1
            prev_hash = latest["block_hash"]
        else:
            next_index = 1
            prev_hash = GENESIS_PREV_HASH

        b_hash = compute_block_hash(
            block_index=next_index,
            created_at=now,
            action_type=action_type,
            payload_hash=payload_hash,
            prev_block_hash=prev_hash,
        )

        conn.execute(
            """
            INSERT INTO audit_blocks (block_index, action_type, payload_json, payload_hash, prev_block_hash, block_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (next_index, action_type, payload_json, payload_hash, prev_hash, b_hash, now),
        )

    return {
        "block_index": next_index,
        "action_type": action_type,
        "payload_hash": payload_hash,
        "prev_block_hash": prev_hash,
        "block_hash": b_hash,
        "created_at": now,
        "is_immutable": True,
    }


def verify_audit_ledger_integrity(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Tüm denetim zincirini baştan sona tarayarak herhangi bir geriye dönük veri tahrifatı olup olmadığını doğrular.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_blocks ORDER BY block_index ASC"
        ).fetchall()

    if not rows:
        return {
            "is_valid": True,
            "total_blocks": 0,
            "latest_block_hash": None,
            "detail": "Denetim zinciri henüz boş (Genesis durumu).",
        }

    expected_prev = GENESIS_PREV_HASH
    for r in rows:
        b_idx = r["block_index"]
        # 1. Önceki blok hash bağlantısı kontrolü
        if r["prev_block_hash"] != expected_prev:
            return {
                "is_valid": False,
                "compromised_block_index": b_idx,
                "error_code": "CHAIN_DISCONTINUITY",
                "detail": f"Blok #{b_idx} zincir bağlantısı kopuk. Önceki blok silinmiş veya sırası bozulmuş.",
            }

        # 2. Payload hash doğrulaması
        recomputed_payload_hash = hashlib.sha256(r["payload_json"].encode("utf-8")).hexdigest()
        if recomputed_payload_hash != r["payload_hash"]:
            return {
                "is_valid": False,
                "compromised_block_index": b_idx,
                "error_code": "PAYLOAD_TAMPERED",
                "detail": f"Blok #{b_idx} veri içeriği sonradan değiştirilmiş.",
            }

        # 3. Blok hash doğrulaması
        recomputed_block_hash = compute_block_hash(
            block_index=b_idx,
            created_at=r["created_at"],
            action_type=r["action_type"],
            payload_hash=recomputed_payload_hash,
            prev_block_hash=expected_prev,
        )

        if recomputed_block_hash != r["block_hash"]:
            return {
                "is_valid": False,
                "compromised_block_index": b_idx,
                "error_code": "BLOCK_HASH_INVALID",
                "detail": f"Blok #{b_idx} kriptografik başlığı geçersiz.",
            }

        expected_prev = r["block_hash"]

    return {
        "is_valid": True,
        "total_blocks": len(rows),
        "latest_block_hash": expected_prev,
        "detail": f"Tüm {len(rows)} blok kusursuz doğrulandı. Veri tabanında geriye dönük tahrifat bulunmuyor.",
    }
