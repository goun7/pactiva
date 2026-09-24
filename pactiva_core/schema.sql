-- Pactiva PostgreSQL 16 + pgvector Kurumsal Şema (pactiva_core/schema.sql)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Kullanıcılar ve Roller (KVKK Uyumlu)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    national_id_hash VARCHAR(64) NOT NULL UNIQUE, -- SHA-256 maskeli TC/Kimlik No
    phone_number_encrypted BYTEA NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('worker', 'employer', 'juror', 'admin')),
    reputation_score NUMERIC(5,2) DEFAULT 100.00 CHECK (reputation_score BETWEEN 0 AND 100),
    is_identity_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. İlanlar ve Pozisyon Bütçesi
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employer_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('film_set', 'construction', 'gig_labor', 'white_collar_talent')),
    base_hourly_rate NUMERIC(10,2) NOT NULL CHECK (base_hourly_rate >= 150.00), -- Yasal asgari saat tabanı
    overtime_multiplier NUMERIC(3,2) DEFAULT 1.50, -- 4857 SK Md. 41 (%50 zam)
    expected_hours NUMERIC(5,2) NOT NULL,
    required_skills_vector vector(1536), -- pgvector yetkinlik vektörü
    is_budget_locked BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'in_progress', 'completed', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Akıllı Emanet Kasası (Smart Escrow Accounts)
CREATE TABLE escrow_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL UNIQUE REFERENCES jobs(id),
    locked_amount NUMERIC(12,2) NOT NULL,
    platform_fee NUMERIC(10,2) NOT NULL, -- %2-%4 altyapı payı
    withholding_tax_reserved NUMERIC(10,2) DEFAULT 0.00, -- GVK 94 %10 stopaj
    currency VARCHAR(3) DEFAULT 'TRY',
    provider_type VARCHAR(20) CHECK (provider_type IN ('bank_virtual_escrow', 'smart_contract_l2')),
    provider_tx_ref VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'locked' CHECK (status IN ('locked', 'disbursed', 'refunded', 'disputed')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Vardiyalar ve PTP Zaman Damgalı Mesai
CREATE TABLE shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id),
    worker_id UUID NOT NULL REFERENCES users(id),
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    actual_check_in TIMESTAMPTZ,
    actual_check_out TIMESTAMPTZ,
    regular_minutes INT DEFAULT 0,
    overtime_minutes INT DEFAULT 0,
    night_shift_minutes INT DEFAULT 0, -- 4857 SK Md. 69 gece mesaisi
    total_gross_payout NUMERIC(10,2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'checked_in', 'completed', 'disputed', 'no_show')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 5. Fiziksel Mesai Doğrulama Olayları
CREATE TABLE attendance_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shift_id UUID NOT NULL REFERENCES shifts(id),
    event_type VARCHAR(20) CHECK (event_type IN ('check_in', 'check_out', 'random_probe')),
    wifi_rtt_distance_meters NUMERIC(6,2),
    ble_beacon_uuid VARCHAR(64),
    cell_tower_cid_lac VARCHAR(50),
    liveness_verification_hash VARCHAR(64) NOT NULL,
    ptp_monotonic_timestamp BIGINT NOT NULL, -- IEEE 1588 donanımsal zaman
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. Çapraz Meslektaş Doğrulamaları (Cross-Peer Attestations)
CREATE TABLE peer_attestations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    worker_id UUID NOT NULL REFERENCES users(id),
    endorser_id UUID NOT NULL REFERENCES users(id),
    job_id UUID NOT NULL REFERENCES jobs(id),
    overlap_start_date DATE NOT NULL,
    overlap_end_date DATE NOT NULL,
    attestation_signature VARCHAR(128) NOT NULL,
    endorser_reputation_weight NUMERIC(3,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_no_self_endorsement CHECK (worker_id <> endorser_id)
);

-- 7. Uyuşmazlıklar ve 7 Üyeli Bağımsız Tahkim
CREATE TABLE disputes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shift_id UUID NOT NULL UNIQUE REFERENCES shifts(id),
    initiator_id UUID NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL,
    evidence_archive_hash VARCHAR(64) NOT NULL, -- SHA-256 kör delil paketi
    resolution_status VARCHAR(20) DEFAULT 'pending' CHECK (resolution_status IN ('pending', 'resolved_worker_favored', 'resolved_employer_favored', 'split_settled')),
    penalty_slashed_amount NUMERIC(10,2) DEFAULT 0.00,
    resolved_at TIMESTAMPTZ
);

CREATE TABLE juror_votes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dispute_id UUID NOT NULL REFERENCES disputes(id),
    juror_id UUID NOT NULL REFERENCES users(id),
    vote_decision VARCHAR(20) CHECK (vote_decision IN ('worker_favor', 'employer_favor', 'split')),
    quadratic_vote_weight NUMERIC(5,2) NOT NULL,
    is_schelling_aligned BOOLEAN,
    juror_reward NUMERIC(10,2) DEFAULT 0.00,
    voted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_juror_dispute UNIQUE (dispute_id, juror_id)
);

-- 8. GİB Elektronik Gider Pusulası ve Vergi Kayıtları
CREATE TABLE tax_invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shift_id UUID NOT NULL UNIQUE REFERENCES shifts(id),
    worker_id UUID NOT NULL REFERENCES users(id),
    gib_invoice_uuid UUID NOT NULL UNIQUE,
    gross_amount NUMERIC(10,2) NOT NULL,
    withholding_tax_amount NUMERIC(10,2) NOT NULL, -- %10 stopaj
    net_payout_amount NUMERIC(10,2) NOT NULL,
    gib_response_status VARCHAR(20) DEFAULT 'reported',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 9. Kriptografik Denetim Zinciri (Proof-of-Audit)
CREATE TABLE audit_blocks (
    block_index BIGINT PRIMARY KEY,
    action_type VARCHAR(64) NOT NULL,
    payload_json JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    prev_block_hash VARCHAR(64) NOT NULL,
    block_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 10. Kurumsal Webhook Abonelikleri ve Olay Dağıtımı
CREATE TABLE webhook_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_url TEXT NOT NULL,
    secret_key TEXT NOT NULL,
    events JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_id UUID NOT NULL REFERENCES webhook_subscriptions(id),
    event_type VARCHAR(64) NOT NULL,
    payload_json JSONB NOT NULL,
    signature_header VARCHAR(64) NOT NULL,
    status_code INTEGER,
    delivery_status VARCHAR(20) DEFAULT 'pending' CHECK (delivery_status IN ('pending', 'delivered', 'failed')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- pgvector ve Performans İndeksleri
CREATE INDEX IF NOT EXISTS idx_jobs_skills ON jobs USING hnsw (required_skills_vector vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_shifts_worker ON shifts(worker_id, scheduled_start);
CREATE INDEX IF NOT EXISTS idx_escrow_status ON escrow_accounts(status);
CREATE INDEX IF NOT EXISTS idx_audit_block_hash ON audit_blocks(block_hash);
CREATE INDEX IF NOT EXISTS idx_webhook_sub_active ON webhook_subscriptions(is_active);
