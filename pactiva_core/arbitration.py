"""
Pactiva — 7 Üyeli Bağımsız Tahkim ve Schelling Karesel Teminat Kesintisi Motoru (pactiva_core/arbitration.py)
Uyuşmazlık durumunda delil paketi, kör oylama, Schelling konsensüsü ve teminat kesintisi (slashing) döngüsü.
"""

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pactiva_core.database import get_db
from pactiva_core.math_models import TWO_PLACES, calculate_quadratic_jury_slashing


def create_dispute(
    shift_id: str,
    initiator_id: str,
    reason: str,
    evidence_archive_hash: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Vardiya için bağımsız uyuşmazlık dosyasını açar ve vardiyayı dondurur.
    """
    dispute_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        job_ref = f"job_disp_{str(shift_id)[:8]}"
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
            VALUES (?, ?, 'enc_phone', 'employer', 100.0, 1, ?)
            """,
            (str(initiator_id), f"hash_{str(initiator_id)[:16]}", now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs (id, employer_id, title, category, base_hourly_rate, overtime_multiplier, expected_hours, is_budget_locked, status, created_at)
            VALUES (?, ?, 'Otomatik İlan', 'gig_labor', 200.0, 1.5, 8.0, 1, 'active', ?)
            """,
            (job_ref, str(initiator_id), now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO shifts (id, job_id, worker_id, scheduled_start, scheduled_end, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'disputed', ?)
            """,
            (str(shift_id), job_ref, str(initiator_id), now, now, now),
        )
        # Shift durumunu disputed yap
        conn.execute("UPDATE shifts SET status = 'disputed' WHERE id = ?", (str(shift_id),))

        conn.execute(
            """
            INSERT INTO disputes (id, shift_id, initiator_id, reason, evidence_archive_hash, resolution_status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (dispute_id, str(shift_id), str(initiator_id), reason, evidence_archive_hash, now),
        )

        row = conn.execute("SELECT * FROM disputes WHERE id = ?", (dispute_id,)).fetchone()
        return dict(row)


def cast_juror_vote(
    dispute_id: str,
    juror_id: str,
    vote_decision: str,
    vote_value: Decimal,
    stake_amount: Decimal,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    7 Üyeli jüri heyetinden bir jürinin kör oyunu ve karesel teminatını kütükler.
    """
    if vote_decision not in ("worker_favor", "employer_favor", "split"):
        raise ValueError("Geçersiz oy kararı.")
    if stake_amount <= Decimal("0.00"):
        raise ValueError("Teminat sıfırdan büyük olmalıdır.")

    quadratic_weight = Decimal(str(math.sqrt(float(stake_amount)))).quantize(TWO_PLACES)
    vote_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
            VALUES (?, ?, 'enc_phone', 'juror', 100.0, 1, ?)
            """,
            (str(juror_id), f"hash_{str(juror_id)[:16]}", now),
        )
        conn.execute(
            """
            INSERT INTO juror_votes (id, dispute_id, juror_id, vote_decision, quadratic_vote_weight, voted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(dispute_id, juror_id) DO UPDATE SET
                vote_decision = excluded.vote_decision,
                quadratic_vote_weight = excluded.quadratic_vote_weight,
                voted_at = excluded.voted_at
            """,
            (vote_id, str(dispute_id), str(juror_id), vote_decision, float(quadratic_weight), now),
        )

        return {
            "vote_id": vote_id,
            "dispute_id": str(dispute_id),
            "juror_id": str(juror_id),
            "vote_decision": vote_decision,
            "vote_value": vote_value,
            "stake_amount": stake_amount,
            "quadratic_vote_weight": quadratic_weight,
            "voted_at": now,
        }


def resolve_dispute(
    dispute_id: str,
    votes_data: List[Dict[str, Any]],
    consensus_threshold: Decimal = Decimal("0.50"),
    slash_rate: Decimal = Decimal("0.30"),
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tüm jüri oylarını toplayarak Schelling konsensüsünü ve teminat kesintisini (slashing) hesaplar.
    """
    if not votes_data:
        raise ValueError("Konsensüs hesabı için en az bir jüri oyu gereklidir.")

    votes: List[Decimal] = [Decimal(str(v["vote_value"])) for v in votes_data]
    stakes: List[Decimal] = [Decimal(str(v["stake_amount"])) for v in votes_data]

    consensus_score, slashed_amounts, juror_rewards = calculate_quadratic_jury_slashing(
        votes=votes,
        stakes=stakes,
        consensus_threshold=consensus_threshold,
        slash_rate=slash_rate,
    )

    if consensus_score >= consensus_threshold:
        outcome = "resolved_worker_favored"
        settlement_desc = "Jüri konsensüsü işçi lehine sonuçlandı. Emanet bütçesi işçiye ödenir."
    elif consensus_score <= -consensus_threshold:
        outcome = "resolved_employer_favored"
        settlement_desc = "Jüri konsensüsü işveren lehine sonuçlandı. Emanet fonu işverene iade edilir."
    else:
        outcome = "split_settled"
        settlement_desc = "Konsensüs barajı aşılamadı; tarafsız uzlaşma ve eşit paylaştırma uygulandı."

    total_slashed = sum(slashed_amounts)
    now = datetime.now(timezone.utc).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            """
            UPDATE disputes
            SET resolution_status = ?, penalty_slashed_amount = ?, resolved_at = ?
            WHERE id = ?
            """,
            (outcome, float(total_slashed), now, str(dispute_id)),
        )

    # Jüri sonuç dökümü
    juror_results = []
    for i, v in enumerate(votes_data):
        juror_results.append({
            "juror_id": v.get("juror_id"),
            "vote_value": votes[i],
            "stake_amount": stakes[i],
            "slashed_amount": slashed_amounts[i],
            "reward_earned": juror_rewards[i],
            "is_honest": slashed_amounts[i] == Decimal("0.00"),
        })

    return {
        "dispute_id": str(dispute_id),
        "resolution_status": outcome,
        "consensus_score": consensus_score,
        "settlement_description": settlement_desc,
        "total_penalty_slashed": total_slashed,
        "juror_count": len(votes_data),
        "juror_results": juror_results,
        "resolved_at": now,
    }
