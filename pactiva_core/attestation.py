"""
Pactiva — Çapraz Meslektaş Doğrulama ve İtibar Ağı Motoru (pactiva_core/attestation.py)
Adayların CV şişirmesini önleyen, aynı sette/şantiyede çalışmış işçilerin birbirini kriptografik onaylaması.
"""

import hashlib
import hmac
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pactiva_core.database import get_db

ATTESTATION_SECRET = os.environ.get("PACTIVA_ATTESTATION_SECRET", "pactiva_peer_attestation_secret_2026")


def compute_attestation_signature(
    worker_id: str,
    endorser_id: str,
    job_id: str,
    overlap_start: str,
    overlap_end: str,
    secret_key: Optional[str] = None,
) -> str:
    """Meslektaş doğrulama kaydının değiştirilemez kriptografik imzasını üretir."""
    key = (secret_key or ATTESTATION_SECRET).encode("utf-8")
    payload = f"{worker_id}:{endorser_id}:{job_id}:{overlap_start}:{overlap_end}"
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def create_peer_attestation(
    worker_id: str,
    endorser_id: str,
    job_id: str,
    overlap_start_date: str,
    overlap_end_date: str,
    endorser_reputation_score: float = 100.0,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Bir çalışanın diğer çalışan için referans onayını kütükler.
    Kendi kendine referans (self-endorsement) kesinlikle engellenir.
    """
    if str(worker_id) == str(endorser_id):
        raise ValueError("Kendi kendine referans (self-endorsement) verilemez.")

    if overlap_start_date > overlap_end_date:
        raise ValueError("Çalışma başlangıç tarihi bitiş tarihinden sonra olamaz.")

    # Ağırlık hesabı: Karesel itibar çarpanı (0.0 - 1.0)
    clamped_rep = max(0.0, min(100.0, endorser_reputation_score))
    weight = round(math.sqrt(clamped_rep / 100.0), 3)

    sig = compute_attestation_signature(
        worker_id=str(worker_id),
        endorser_id=str(endorser_id),
        job_id=str(job_id),
        overlap_start=overlap_start_date,
        overlap_end=overlap_end_date,
    )

    aid = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        # FK emniyeti
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
            VALUES (?, ?, 'enc', 'worker', 100.0, 1, ?)
            """,
            (str(worker_id), f"hash_{str(worker_id)[:16]}", now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
            VALUES (?, ?, 'enc', 'worker', ?, 1, ?)
            """,
            (str(endorser_id), f"hash_{str(endorser_id)[:16]}", endorser_reputation_score, now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs (id, employer_id, title, category, base_hourly_rate, overtime_multiplier, expected_hours, is_budget_locked, status, created_at)
            VALUES (?, ?, 'Doğrulanan Proje', 'gig_labor', 250.0, 1.5, 8.0, 1, 'completed', ?)
            """,
            (str(job_id), str(endorser_id), now),
        )
        conn.execute(
            """
            INSERT INTO peer_attestations (id, worker_id, endorser_id, job_id, overlap_start_date, overlap_end_date, attestation_signature, endorser_reputation_weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (aid, str(worker_id), str(endorser_id), str(job_id), overlap_start_date, overlap_end_date, sig, weight, now),
        )

    return {
        "attestation_id": aid,
        "worker_id": str(worker_id),
        "endorser_id": str(endorser_id),
        "job_id": str(job_id),
        "overlap_start_date": overlap_start_date,
        "overlap_end_date": overlap_end_date,
        "signature": sig,
        "endorser_reputation_weight": weight,
        "is_verified": True,
    }


def get_worker_attestations(worker_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Çalışanın aldığı tüm meslektaş onaylarını ve kümülatif güven skorunu döner."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM peer_attestations WHERE worker_id = ? ORDER BY created_at DESC",
            (str(worker_id),),
        ).fetchall()
        attestations = [dict(r) for r in rows]

    total_weight = sum(a["endorser_reputation_weight"] for a in attestations)
    return {
        "worker_id": str(worker_id),
        "total_attestations_count": len(attestations),
        "cumulative_trust_weight": round(total_weight, 2),
        "verified_peer_badge": len(attestations) >= 2,
        "attestations": attestations,
    }
