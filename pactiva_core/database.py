"""
Pactiva — Veritabanı Altyapısı (pactiva_core/database.py)
SQLite WAL / PostgreSQL uyumlu kurumsal kalıcılık katmanı.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

DEFAULT_DB_PATH = os.environ.get("PACTIVA_DB_PATH", "pactiva.db")

SQLITE_SCHEMA_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- 1. Kullanıcılar ve Roller (KVKK Uyumlu)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    national_id_hash TEXT NOT NULL UNIQUE,
    phone_number_encrypted TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('worker', 'employer', 'juror', 'admin')),
    reputation_score REAL DEFAULT 100.00 CHECK (reputation_score BETWEEN 0 AND 100),
    is_identity_verified INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- 2. İlanlar ve Pozisyon Bütçesi
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    employer_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('film_set', 'construction', 'gig_labor', 'white_collar_talent')),
    base_hourly_rate REAL NOT NULL CHECK (base_hourly_rate >= 150.00),
    overtime_multiplier REAL DEFAULT 1.50,
    expected_hours REAL NOT NULL,
    required_skills_vector TEXT,
    is_budget_locked INTEGER DEFAULT 0,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'in_progress', 'completed', 'cancelled')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (employer_id) REFERENCES users(id)
);

-- 3. Akıllı Emanet Kasası (Smart Escrow Accounts)
CREATE TABLE IF NOT EXISTS escrow_accounts (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    locked_amount REAL NOT NULL,
    platform_fee REAL NOT NULL,
    withholding_tax_reserved REAL DEFAULT 0.00,
    currency TEXT DEFAULT 'TRY',
    provider_type TEXT CHECK (provider_type IN ('bank_virtual_escrow', 'smart_contract_l2')),
    provider_tx_ref TEXT NOT NULL,
    status TEXT DEFAULT 'locked' CHECK (status IN ('locked', 'disbursed', 'refunded', 'disputed')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- 4. Vardiyalar ve PTP Zaman Damgalı Mesai
CREATE TABLE IF NOT EXISTS shifts (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    scheduled_start TEXT NOT NULL,
    scheduled_end TEXT NOT NULL,
    actual_check_in TEXT,
    actual_check_out TEXT,
    regular_minutes INTEGER DEFAULT 0,
    overtime_minutes INTEGER DEFAULT 0,
    night_shift_minutes INTEGER DEFAULT 0,
    total_gross_payout REAL DEFAULT 0.00,
    status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'checked_in', 'completed', 'disputed', 'no_show')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (worker_id) REFERENCES users(id)
);

-- 5. Fiziksel Mesai Doğrulama Olayları
CREATE TABLE IF NOT EXISTS attendance_events (
    id TEXT PRIMARY KEY,
    shift_id TEXT NOT NULL,
    event_type TEXT CHECK (event_type IN ('check_in', 'check_out', 'random_probe')),
    wifi_rtt_distance_meters REAL,
    ble_beacon_uuid TEXT,
    cell_tower_cid_lac TEXT,
    liveness_verification_hash TEXT NOT NULL,
    ptp_monotonic_timestamp INTEGER NOT NULL,
    is_verified INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (shift_id) REFERENCES shifts(id)
);

-- 6. Çapraz Meslektaş Doğrulamaları (Peer Attestations)
CREATE TABLE IF NOT EXISTS peer_attestations (
    id TEXT PRIMARY KEY,
    worker_id TEXT NOT NULL,
    endorser_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    overlap_start_date TEXT NOT NULL,
    overlap_end_date TEXT NOT NULL,
    attestation_signature TEXT NOT NULL,
    endorser_reputation_weight REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (worker_id) REFERENCES users(id),
    FOREIGN KEY (endorser_id) REFERENCES users(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    CHECK (worker_id != endorser_id)
);

-- 7. Uyuşmazlıklar ve 7 Üyeli Bağımsız Tahkim
CREATE TABLE IF NOT EXISTS disputes (
    id TEXT PRIMARY KEY,
    shift_id TEXT NOT NULL UNIQUE,
    initiator_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_archive_hash TEXT NOT NULL,
    resolution_status TEXT DEFAULT 'pending' CHECK (resolution_status IN ('pending', 'resolved_worker_favored', 'resolved_employer_favored', 'split_settled')),
    penalty_slashed_amount REAL DEFAULT 0.00,
    resolved_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (shift_id) REFERENCES shifts(id),
    FOREIGN KEY (initiator_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS juror_votes (
    id TEXT PRIMARY KEY,
    dispute_id TEXT NOT NULL,
    juror_id TEXT NOT NULL,
    vote_decision TEXT CHECK (vote_decision IN ('worker_favor', 'employer_favor', 'split')),
    quadratic_vote_weight REAL NOT NULL,
    is_schelling_aligned INTEGER,
    juror_reward REAL DEFAULT 0.00,
    voted_at TEXT NOT NULL,
    FOREIGN KEY (dispute_id) REFERENCES disputes(id),
    FOREIGN KEY (juror_id) REFERENCES users(id),
    UNIQUE(dispute_id, juror_id)
);

-- 8. GİB Elektronik Gider Pusulası ve Vergi Kayıtları
CREATE TABLE IF NOT EXISTS tax_invoices (
    id TEXT PRIMARY KEY,
    shift_id TEXT NOT NULL UNIQUE,
    worker_id TEXT NOT NULL,
    gib_invoice_uuid TEXT NOT NULL UNIQUE,
    gross_amount REAL NOT NULL,
    withholding_tax_amount REAL NOT NULL,
    net_payout_amount REAL NOT NULL,
    gib_response_status TEXT DEFAULT 'reported',
    created_at TEXT NOT NULL,
    FOREIGN KEY (shift_id) REFERENCES shifts(id),
    FOREIGN KEY (worker_id) REFERENCES users(id)
);

-- 9. Kriptografik Denetim Zinciri (Proof-of-Audit)
CREATE TABLE IF NOT EXISTS audit_blocks (
    block_index INTEGER PRIMARY KEY,
    action_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    prev_block_hash TEXT NOT NULL,
    block_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

-- 10. Kurumsal Webhook Abonelikleri ve Olay Dağıtımı
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id TEXT PRIMARY KEY,
    target_url TEXT NOT NULL,
    secret_key TEXT NOT NULL,
    events TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    signature_header TEXT NOT NULL,
    status_code INTEGER,
    delivery_status TEXT DEFAULT 'pending' CHECK (delivery_status IN ('pending', 'delivered', 'failed')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (subscription_id) REFERENCES webhook_subscriptions(id)
);

-- İndeksler
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_escrows_status ON escrow_accounts(status);
CREATE INDEX IF NOT EXISTS idx_shifts_worker ON shifts(worker_id, scheduled_start);
CREATE INDEX IF NOT EXISTS idx_attendance_shift ON attendance_events(shift_id);
CREATE INDEX IF NOT EXISTS idx_audit_block_hash ON audit_blocks(block_hash);
CREATE INDEX IF NOT EXISTS idx_webhook_sub_active ON webhook_subscriptions(is_active);
"""


def init_db(db_path: Optional[str] = None) -> None:
    """Veritabanı tablolarını ve WAL modunu başlatır."""
    target_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(target_path)
    try:
        conn.executescript(SQLITE_SCHEMA_DDL)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """İşlem güvenliği sağlayan veritabanı bağlantı yöneticisi."""
    target_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
