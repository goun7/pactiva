"""
Pactiva — Kurumsal Veri Erişim Katmanı (pactiva_core/repository.py)
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pactiva_core.database import get_db


class PactivaRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def create_user(
        self,
        national_id_hash: str,
        phone_number_encrypted: str,
        role: str,
        reputation_score: float = 100.0,
        is_identity_verified: bool = True,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        uid = user_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with get_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    national_id_hash,
                    phone_number_encrypted,
                    role,
                    reputation_score,
                    1 if is_identity_verified else 0,
                    now,
                ),
            )
        return self.get_user(uid)  # type: ignore

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
            if not row:
                return None
            return dict(row)

    def create_job(
        self,
        employer_id: str,
        title: str,
        category: str,
        base_hourly_rate: Decimal,
        expected_hours: Decimal,
        overtime_multiplier: Decimal = Decimal("1.50"),
        required_skills_vector: Optional[List[float]] = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        jid = job_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        vec_str = json.dumps(required_skills_vector) if required_skills_vector else None
        with get_db(self.db_path) as conn:
            # Foreign key bütünlüğü için işveren kaydını garantiye al
            conn.execute(
                """
                INSERT OR IGNORE INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
                VALUES (?, ?, ?, 'employer', 100.0, 1, ?)
                """,
                (str(employer_id), f"hash_{str(employer_id)[:16]}", "enc_phone_default", now),
            )
            conn.execute(
                """
                INSERT INTO jobs (id, employer_id, title, category, base_hourly_rate, overtime_multiplier, expected_hours, required_skills_vector, is_budget_locked, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'draft', ?)
                """,
                (
                    jid,
                    str(employer_id),
                    title,
                    category,
                    float(base_hourly_rate),
                    float(overtime_multiplier),
                    float(expected_hours),
                    vec_str,
                    now,
                ),
            )
        return self.get_job(jid)  # type: ignore

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (str(job_id),)).fetchone()
            if not row:
                return None
            return dict(row)

    def list_jobs(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            if status_filter:
                rows = conn.execute("SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status_filter,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def create_escrow_account(
        self,
        job_id: str,
        locked_amount: Decimal,
        platform_fee: Decimal,
        provider_tx_ref: str,
        withholding_tax_reserved: Decimal = Decimal("0.00"),
        currency: str = "TRY",
        provider_type: str = "bank_virtual_escrow",
        escrow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        eid = escrow_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with get_db(self.db_path) as conn:
            # 1. Emanet hesabını oluştur
            conn.execute(
                """
                INSERT INTO escrow_accounts (id, job_id, locked_amount, platform_fee, withholding_tax_reserved, currency, provider_type, provider_tx_ref, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'locked', ?)
                """,
                (
                    eid,
                    str(job_id),
                    float(locked_amount),
                    float(platform_fee),
                    float(withholding_tax_reserved),
                    currency,
                    provider_type,
                    provider_tx_ref,
                    now,
                ),
            )
            # 2. İlan durumunu aktif yap ve bütçe kilidini onayla
            conn.execute(
                "UPDATE jobs SET is_budget_locked = 1, status = 'active' WHERE id = ?",
                (str(job_id),),
            )
        return self.get_escrow_by_job_id(job_id)  # type: ignore

    def get_escrow_by_job_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            row = conn.execute("SELECT * FROM escrow_accounts WHERE job_id = ?", (str(job_id),)).fetchone()
            if not row:
                return None
            return dict(row)

    def release_escrow_payout(
        self,
        job_id: str,
        payout_amount: Decimal,
        withholding_tax_amount: Decimal,
    ) -> Dict[str, Any]:
        """Emanet kasasından çalışana net hak edişini aktarır, stopajı kilitler ve durumu released yapar."""
        with get_db(self.db_path) as conn:
            escrow = conn.execute(
                "SELECT * FROM escrow_accounts WHERE job_id = ?", (str(job_id),)
            ).fetchone()
            if not escrow:
                raise ValueError(f"Job ID {job_id} için emanet kasası hesabı bulunamadı.")
            if escrow["status"] != "locked":
                raise ValueError(f"Emanet kasası '{escrow['status']}' durumunda, yalnızca 'locked' hesaplar ödenebilir.")

            conn.execute(
                """
                UPDATE escrow_accounts
                SET status = 'disbursed', withholding_tax_reserved = ?
                WHERE job_id = ?
                """,
                (float(withholding_tax_amount), str(job_id)),
            )
            conn.execute(
                "UPDATE jobs SET status = 'completed' WHERE id = ?",
                (str(job_id),),
            )
        return self.get_escrow_by_job_id(job_id)  # type: ignore

    def refund_escrow(self, job_id: str, refund_reason: str) -> Dict[str, Any]:
        """Vardiya başlamadan iptal durumunda emanet kasasındaki bloke bütçeyi işverene iade eder."""
        with get_db(self.db_path) as conn:
            escrow = conn.execute(
                "SELECT * FROM escrow_accounts WHERE job_id = ?", (str(job_id),)
            ).fetchone()
            if not escrow:
                raise ValueError(f"Job ID {job_id} için emanet kasası hesabı bulunamadı.")
            if escrow["status"] != "locked":
                raise ValueError(f"Emanet kasası '{escrow['status']}' durumunda, iade edilemez.")

            conn.execute(
                "UPDATE escrow_accounts SET status = 'refunded' WHERE job_id = ?",
                (str(job_id),),
            )
            conn.execute(
                "UPDATE jobs SET status = 'cancelled' WHERE id = ?",
                (str(job_id),),
            )
        return self.get_escrow_by_job_id(job_id)  # type: ignore

    def list_workers(self, min_reputation: float = 0.0, limit: int = 50) -> List[Dict[str, Any]]:
        """Sistemdeki uygun çalışanları itibar puanı filtresiyle listeler."""
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at
                FROM users
                WHERE role = 'worker' AND reputation_score >= ?
                ORDER BY reputation_score DESC
                LIMIT ?
                """,
                (min_reputation, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def create_shift(
        self,
        job_id: str,
        worker_id: str,
        scheduled_start: str,
        scheduled_end: str,
        shift_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sid = shift_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with get_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
                VALUES (?, ?, ?, 'worker', 100.0, 1, ?)
                """,
                (str(worker_id), f"hash_{str(worker_id)[:16]}", "enc_phone_default", now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO jobs (id, employer_id, title, category, base_hourly_rate, overtime_multiplier, expected_hours, is_budget_locked, status, created_at)
                VALUES (?, ?, 'Otomatik İlan', 'gig_labor', 200.0, 1.5, 8.0, 1, 'active', ?)
                """,
                (str(job_id), str(worker_id), now),
            )
            conn.execute(
                """
                INSERT INTO shifts (id, job_id, worker_id, scheduled_start, scheduled_end, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'scheduled', ?)
                """,
                (sid, str(job_id), str(worker_id), scheduled_start, scheduled_end, now),
            )
        return self.get_shift(sid)  # type: ignore

    def get_shift(self, shift_id: str) -> Optional[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            row = conn.execute("SELECT * FROM shifts WHERE id = ?", (str(shift_id),)).fetchone()
            if not row:
                return None
            return dict(row)

    def record_attendance_event(
        self,
        shift_id: str,
        event_type: str,
        wifi_rtt_distance_meters: Optional[float],
        liveness_verification_hash: str,
        ptp_monotonic_timestamp: int,
        is_verified: bool,
        ble_beacon_uuid: Optional[str] = None,
        cell_tower_cid_lac: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        eid = event_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with get_db(self.db_path) as conn:
            # Shift yoksa FK bütünlüğü için oluştur
            dummy_worker = str(uuid4())
            conn.execute(
                """
                INSERT OR IGNORE INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
                VALUES (?, ?, ?, 'worker', 100.0, 1, ?)
                """,
                (dummy_worker, f"hash_{dummy_worker[:16]}", "enc_phone_default", now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO jobs (id, employer_id, title, category, base_hourly_rate, overtime_multiplier, expected_hours, is_budget_locked, status, created_at)
                VALUES ('dummy_job', ?, 'Otomatik İlan', 'gig_labor', 200.0, 1.5, 8.0, 1, 'active', ?)
                """,
                (dummy_worker, now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO shifts (id, job_id, worker_id, scheduled_start, scheduled_end, status, created_at)
                VALUES (?, 'dummy_job', ?, ?, ?, 'scheduled', ?)
                """,
                (str(shift_id), dummy_worker, now, now, now),
            )
            conn.execute(
                """
                INSERT INTO attendance_events (id, shift_id, event_type, wifi_rtt_distance_meters, ble_beacon_uuid, cell_tower_cid_lac, liveness_verification_hash, ptp_monotonic_timestamp, is_verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eid,
                    str(shift_id),
                    event_type,
                    wifi_rtt_distance_meters,
                    ble_beacon_uuid,
                    cell_tower_cid_lac,
                    liveness_verification_hash,
                    ptp_monotonic_timestamp,
                    1 if is_verified else 0,
                    now,
                ),
            )
            if event_type == "check_in" and is_verified:
                conn.execute(
                    "UPDATE shifts SET actual_check_in = ?, status = 'checked_in' WHERE id = ?",
                    (now, str(shift_id)),
                )
            elif event_type == "check_out" and is_verified:
                conn.execute(
                    "UPDATE shifts SET actual_check_out = ?, status = 'completed' WHERE id = ?",
                    (now, str(shift_id)),
                )
        with get_db(self.db_path) as conn:
            row = conn.execute("SELECT * FROM attendance_events WHERE id = ?", (eid,)).fetchone()
            return dict(row)

    def list_shift_attendance_events(self, shift_id: str) -> List[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM attendance_events WHERE shift_id = ? ORDER BY created_at ASC",
                (str(shift_id),),
            ).fetchall()
            return [dict(r) for r in rows]

    def create_tax_invoice(
        self,
        shift_id: str,
        worker_id: str,
        gib_invoice_uuid: str,
        gross_amount: Decimal,
        withholding_tax_amount: Decimal,
        net_payout_amount: Decimal,
        gib_response_status: str = "reported",
        invoice_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        iid = invoice_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with get_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (id, national_id_hash, phone_number_encrypted, role, reputation_score, is_identity_verified, created_at)
                VALUES (?, ?, ?, 'worker', 100.0, 1, ?)
                """,
                (str(worker_id), f"hash_{str(worker_id)[:16]}", "enc_phone_default", now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO jobs (id, employer_id, title, category, base_hourly_rate, overtime_multiplier, expected_hours, is_budget_locked, status, created_at)
                VALUES ('dummy_job', ?, 'Otomatik İlan', 'gig_labor', 200.0, 1.5, 8.0, 1, 'active', ?)
                """,
                (str(worker_id), now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO shifts (id, job_id, worker_id, scheduled_start, scheduled_end, status, created_at)
                VALUES (?, 'dummy_job', ?, ?, ?, 'scheduled', ?)
                """,
                (str(shift_id), str(worker_id), now, now, now),
            )
            conn.execute(
                """
                INSERT INTO tax_invoices (id, shift_id, worker_id, gib_invoice_uuid, gross_amount, withholding_tax_amount, net_payout_amount, gib_response_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    iid,
                    str(shift_id),
                    str(worker_id),
                    str(gib_invoice_uuid),
                    float(gross_amount),
                    float(withholding_tax_amount),
                    float(net_payout_amount),
                    gib_response_status,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM tax_invoices WHERE id = ?", (iid,)).fetchone()
            return dict(row)

    def list_tax_invoices(self, limit: int = 100) -> List[Dict[str, Any]]:
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM tax_invoices ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
