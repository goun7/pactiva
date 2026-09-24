"""
Pactiva API Veri Modelleri ve Şemaları (pactiva_core/schemas.py)
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


class JobEscrowLockRequest(BaseModel):
    employer_id: UUID
    title: str = Field(..., min_length=3, max_length=150)
    category: str = Field(..., pattern="^(film_set|construction|gig_labor|white_collar_talent)$")
    base_hourly_rate: Decimal = Field(..., ge=Decimal("150.00"), description="Yasal taban saatlik ücret (TL)")
    expected_hours: Decimal = Field(..., gt=Decimal("0.0"), description="Öngörülen çalışma süresi (saat)")
    overtime_multiplier: Decimal = Field(default=Decimal("1.50"), ge=Decimal("1.0"), le=Decimal("2.0"))
    escrow_provider: str = Field(default="bank_virtual_escrow", pattern="^(bank_virtual_escrow|smart_contract_l2)$")


class JobEscrowLockResponse(BaseModel):
    job_id: UUID
    escrow_account_id: UUID
    title: str
    status: str
    is_budget_locked: bool
    locked_amount: Decimal
    platform_fee: Decimal
    escrow_tx_ref: str
    active_hiring_verified: bool


class WiFiRTTTelemetry(BaseModel):
    access_points_measured: int = Field(..., ge=1)
    distance_meters: float = Field(..., ge=0.0)
    accuracy_meters: float = Field(..., ge=0.0)


class AttendanceCheckInRequest(BaseModel):
    shift_id: UUID
    worker_id: UUID
    wifi_rtt_telemetry: Optional[WiFiRTTTelemetry] = None
    ble_beacon_id: Optional[str] = None
    liveness_hash: str = Field(..., min_length=32, max_length=128)
    client_monotonic_ptp: int = Field(..., gt=0, description="Cihaz donanımsal zaman damgası")


class AttendanceCheckInResponse(BaseModel):
    event_id: UUID
    shift_id: UUID
    worker_id: UUID
    shift_status: str
    actual_check_in: str
    is_verified: bool
    distance_verified: bool
    ptp_time_synchronized: bool
    overtime_auto_calculator_active: bool


class GIBInvoiceRequest(BaseModel):
    shift_id: UUID
    worker_id: UUID
    gross_amount: Optional[Decimal] = None
    net_payout: Optional[Decimal] = None
    withholding_tax_rate: Decimal = Field(default=Decimal("0.10"), ge=Decimal("0.0"), lt=Decimal("1.0"))

    @field_validator("net_payout", mode="after")
    @classmethod
    def validate_amounts(cls, v, info):
        gross = info.data.get("gross_amount")
        if v is None and gross is None:
            raise ValueError("Brüt tutar veya net tutardan en az biri belirtilmelidir.")
        return v


class GIBInvoiceResponse(BaseModel):
    gib_invoice_uuid: UUID
    shift_id: UUID
    worker_id: UUID
    gross_amount: Decimal
    withholding_tax_deducted: Decimal
    net_payout: Decimal
    tax_rate_applied: Decimal
    gib_portal_signed: bool
    pdf_archive_url: str


class JuryVoteRequest(BaseModel):
    dispute_id: UUID
    juror_id: UUID
    vote_decision: str = Field(..., pattern="^(worker_favor|employer_favor|split)$")
    vote_value: Decimal = Field(..., ge=Decimal("-1.0"), le=Decimal("1.0"))
    stake_amount: Decimal = Field(..., gt=Decimal("0.0"))


class JuryVoteResponse(BaseModel):
    dispute_id: UUID
    juror_id: UUID
    vote_decision: str
    quadratic_vote_weight: Decimal
    status: str


class RollingQRGenerateRequest(BaseModel):
    job_id: UUID
    shift_id: UUID


class RollingQRGenerateResponse(BaseModel):
    token: str
    job_id: UUID
    shift_id: UUID
    window_step: int
    nonce: str
    seconds_remaining: int
    expires_at_epoch: int


class RollingQRVerifyRequest(BaseModel):
    token: str
    job_id: UUID
    shift_id: UUID
    worker_id: UUID
    wifi_rtt_telemetry: Optional[WiFiRTTTelemetry] = None
    liveness_hash: str = Field(..., min_length=16, max_length=128)
    client_monotonic_ptp: int = Field(..., gt=0)


class RollingQRVerifyResponse(BaseModel):
    is_valid: bool
    event_id: Optional[UUID] = None
    shift_id: UUID
    worker_id: UUID
    detail: str
    is_verified: bool
    distance_verified: bool
    actual_check_in: Optional[str] = None


class EmergencyDispatchRequest(BaseModel):
    job_id: UUID
    shift_id: UUID
    base_hourly_rate: Decimal = Field(..., ge=Decimal("150.00"))
    candidates_pool: Optional[list] = None


class EmergencyDispatchResponse(BaseModel):
    success: bool
    job_id: UUID
    shift_id: UUID
    status: str
    message: Optional[str] = None
    primary_assigned_candidate: Optional[dict] = None
    standby_pool_size: int = 0
    base_hourly_rate: Decimal
    rush_hourly_rate: Decimal
    rush_premium_hourly: Decimal
    sla_target_minutes: int = 10
    estimated_arrival_minutes: Optional[int] = None


class PeerAttestationCreateRequest(BaseModel):
    worker_id: UUID
    endorser_id: UUID
    job_id: UUID
    overlap_start_date: str
    overlap_end_date: str
    endorser_reputation_score: float = Field(default=100.0, ge=0.0, le=100.0)


class PeerAttestationCreateResponse(BaseModel):
    attestation_id: UUID
    worker_id: UUID
    endorser_id: UUID
    job_id: UUID
    overlap_start_date: str
    overlap_end_date: str
    signature: str
    endorser_reputation_weight: float
    is_verified: bool


class SkillMatchRequest(BaseModel):
    job_skills: list[str] = Field(..., min_length=1)
    candidates: list[dict] = Field(..., min_length=1)
    min_match_threshold: float = Field(default=0.40, ge=0.0, le=1.0)


class SkillMatchResponse(BaseModel):
    job_skills: list[str]
    total_candidates_evaluated: int
    ranked_matches: list[dict]


class DisputeCreateRequest(BaseModel):
    shift_id: UUID
    initiator_id: UUID
    reason: str = Field(..., min_length=5)
    evidence_archive_hash: str = Field(..., min_length=16)


class DisputeCreateResponse(BaseModel):
    id: UUID
    shift_id: UUID
    initiator_id: UUID
    reason: str
    evidence_archive_hash: str
    resolution_status: str


class DisputeResolveRequest(BaseModel):
    votes: list[dict] = Field(..., min_length=1)
    consensus_threshold: Decimal = Field(default=Decimal("0.50"), ge=Decimal("0.1"), le=Decimal("1.0"))
    slash_rate: Decimal = Field(default=Decimal("0.30"), ge=Decimal("0.0"), le=Decimal("1.0"))


class DisputeResolveResponse(BaseModel):
    dispute_id: UUID
    resolution_status: str
    consensus_score: Decimal
    settlement_description: str
    total_penalty_slashed: Decimal
    juror_count: int
    juror_results: list[dict]
    resolved_at: str


class LivenessCheckRequest(BaseModel):
    tap_intervals_ms: list[float] = Field(..., min_length=3)
    touch_radii: Optional[list[float]] = None


class LivenessCheckResponse(BaseModel):
    is_human: bool
    average_reaction_ms: Optional[float] = None
    jitter_std_dev_ms: Optional[float] = None
    timing_entropy_bits: Optional[float] = None
    liveness_hash: Optional[str] = None
    detail: str


class ContractGenerateRequest(BaseModel):
    employer_id: UUID
    worker_id: UUID
    job_id: UUID
    job_title: str = Field(..., min_length=3)
    base_hourly_rate: Decimal = Field(..., ge=Decimal("150.00"))
    expected_hours: Decimal = Field(..., gt=Decimal("0.0"))
    category: str = Field(..., pattern="^(film_set|construction|gig_labor|white_collar_talent)$")


class ContractGenerateResponse(BaseModel):
    contract_id: UUID
    employer_id: UUID
    worker_id: UUID
    job_id: UUID
    job_title: str
    category: str
    base_hourly_rate: Decimal
    expected_hours: Decimal
    estimated_total_payout: Decimal
    statutory_compliance: dict
    contract_sha256_hash: str
    canonical_clauses: list[str]
    archive_url: str
    created_at: str
    is_digitally_signed: bool


class PTPSyncRequest(BaseModel):
    client_ptp_timestamp_ns: int = Field(..., gt=0)
    previous_event_ptp_ns: Optional[int] = None
    estimated_network_rtt_ns: int = Field(default=40_000_000, ge=0)


class PTPSyncResponse(BaseModel):
    is_synchronized: bool
    clock_offset_ms: Optional[float] = None
    master_timestamp_ns: Optional[int] = None
    client_timestamp_ns: Optional[int] = None
    ptp_jitter_ms: Optional[float] = None
    error_code: Optional[str] = None
    detail: str


class ERPExportRequest(BaseModel):
    format: str = Field(default="json", pattern="^(json|logo_xml|sap_csv)$")
    account_cost_center: str = Field(default="740.01.001")


class ERPExportResponse(BaseModel):
    format: str
    total_entries: int
    total_gross: Decimal
    total_tax: Decimal
    total_net: Decimal
    export_payload: str


class OfflineEventItem(BaseModel):
    shift_id: UUID
    worker_id: UUID
    ptp_monotonic_timestamp_ns: int = Field(..., gt=0)
    wifi_rtt_distance_meters: float = Field(..., ge=0.0)
    event_type: str = Field(default="check_in", pattern="^(check_in|check_out|probe)$")
    event_hash: Optional[str] = None


class OfflineBatchSyncRequest(BaseModel):
    events: list[OfflineEventItem] = Field(..., min_length=1)


class OfflineBatchSyncResponse(BaseModel):
    success: bool
    synced_count: int
    final_block_hash: Optional[str] = None
    detail: str


class AuditRecordRequest(BaseModel):
    action_type: str = Field(..., min_length=3)
    payload: dict


class AuditRecordResponse(BaseModel):
    block_index: int
    action_type: str
    payload_hash: str
    prev_block_hash: str
    block_hash: str
    created_at: str
    is_immutable: bool


class AuditVerifyResponse(BaseModel):
    is_valid: bool
    total_blocks: int
    latest_block_hash: Optional[str] = None
    detail: str


class ContractVerifyRequest(BaseModel):
    canonical_clauses: list[str] = Field(..., min_length=1)
    expected_hash: str = Field(..., min_length=64, max_length=64)


class ContractVerifyResponse(BaseModel):
    is_valid: bool
    computed_hash: str
    expected_hash: str
    statutory_compliance_status: str
    detail: str


class EscrowReleaseRequest(BaseModel):
    job_id: UUID
    payout_amount: Decimal = Field(..., gt=Decimal("0.00"))
    withholding_tax_amount: Decimal = Field(..., ge=Decimal("0.00"))


class EscrowReleaseResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str
    payout_amount: Decimal
    withholding_tax_amount: Decimal
    audit_block_hash: str
    detail: str


class EscrowRefundRequest(BaseModel):
    job_id: UUID
    refund_reason: str = Field(..., min_length=5)


class EscrowRefundResponse(BaseModel):
    success: bool
    job_id: UUID
    status: str
    refund_reason: str
    audit_block_hash: str
    detail: str


class WebhookSubscribeRequest(BaseModel):
    target_url: str = Field(..., pattern="^https?://.+")
    secret_key: str = Field(..., min_length=16)
    events: list[str] = Field(default=["*"], min_length=1)


class WebhookSubscribeResponse(BaseModel):
    id: UUID
    target_url: str
    events: list[str]
    is_active: bool
    created_at: str


class WebhookDispatchTestRequest(BaseModel):
    event_type: str = Field(..., min_length=3)
    payload: dict


class WebhookDispatchTestResponse(BaseModel):
    event: str
    dispatched_count: int
    deliveries: list[dict]
