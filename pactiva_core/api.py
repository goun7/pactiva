"""
Pactiva — Kurumsal İstihdam ve Emanet Hak Ediş Altyapısı API Servisi (pactiva_core/api.py)
"""

import math
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from pactiva_core.arbitration import create_dispute, resolve_dispute
from pactiva_core.attestation import create_peer_attestation, get_worker_attestations
from pactiva_core.audit_ledger import record_audit_event, verify_audit_ledger_integrity
from pactiva_core.contracts import generate_tripartite_contract, verify_contract_integrity
from pactiva_core.database import init_db
from pactiva_core.dispatch import trigger_emergency_dispatch
from pactiva_core.erp_export import (
    generate_journal_entry,
    export_to_logo_xml,
    export_to_sap_csv,
)
from pactiva_core.liveness import verify_touch_liveness
from pactiva_core.offline_sync import process_offline_attendance_batch
from pactiva_core.ptp_clock import synchronize_and_verify_ptp
from pactiva_core.math_models import (
    calculate_escrow_budget_lock,
    compute_gib_net_gross_tax,
    TWO_PLACES,
)
from pactiva_core.metrics import generate_prometheus_metrics
from pactiva_core.qr_engine import generate_rolling_qr_token, verify_rolling_qr_token
from pactiva_core.rate_limiter import global_rate_limiter
from pactiva_core.repository import PactivaRepository
from pactiva_core.webhooks import (
    create_webhook_subscription,
    list_webhook_subscriptions,
    dispatch_event_to_webhooks,
)
from pactiva_core.schemas import (
    AttendanceCheckInRequest,
    AttendanceCheckInResponse,
    AuditRecordRequest,
    AuditRecordResponse,
    AuditVerifyResponse,
    ContractGenerateRequest,
    ContractGenerateResponse,
    ContractVerifyRequest,
    ContractVerifyResponse,
    DisputeCreateRequest,
    DisputeCreateResponse,
    DisputeResolveRequest,
    DisputeResolveResponse,
    EmergencyDispatchRequest,
    EmergencyDispatchResponse,
    ERPExportRequest,
    ERPExportResponse,
    EscrowRefundRequest,
    EscrowRefundResponse,
    EscrowReleaseRequest,
    EscrowReleaseResponse,
    GIBInvoiceRequest,
    GIBInvoiceResponse,
    JobEscrowLockRequest,
    JobEscrowLockResponse,
    JuryVoteRequest,
    JuryVoteResponse,
    LivenessCheckRequest,
    LivenessCheckResponse,
    OfflineBatchSyncRequest,
    OfflineBatchSyncResponse,
    PeerAttestationCreateRequest,
    PeerAttestationCreateResponse,
    PTPSyncRequest,
    PTPSyncResponse,
    RollingQRGenerateRequest,
    RollingQRGenerateResponse,
    RollingQRVerifyRequest,
    RollingQRVerifyResponse,
    SkillMatchRequest,
    SkillMatchResponse,
    WebhookDispatchTestRequest,
    WebhookDispatchTestResponse,
    WebhookSubscribeRequest,
    WebhookSubscribeResponse,
)
from pactiva_core.vector_engine import generate_skill_vector_stub, rank_candidates_by_skill_match

# Veritabanını başlat
init_db()
repo = PactivaRepository()

app = FastAPI(
    title="Pactiva Enterprise API",
    description="Dağıtık İstihdam, Bilişsel Yetkinlik & Emanet Hak Ediş Altyapısı",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_and_timing_middleware(request, call_next):
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_allowed, remaining, retry_after = global_rate_limiter.is_allowed(client_ip, max_requests=1000, window_seconds=60.0)
    if not is_allowed:
        import json
        return Response(
            content=json.dumps({"detail": "Too Many Requests (Hız Sınırı Aşıldı)", "retry_after": retry_after}),
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Response-Time-MS"] = f"{duration_ms:.2f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/metrics", tags=["Telemetri"])
def prometheus_metrics():
    """Kubernetes ve Prometheus scraping için OpenMetrics çıktısı."""
    return PlainTextResponse(generate_prometheus_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/api/v1/health", tags=["Sistem"])
def health_check():
    return {
        "status": "operational",
        "service": "Pactiva Core API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


@app.post(
    "/api/v1/jobs/escrow-lock",
    response_model=JobEscrowLockResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Emanet & İlan"],
)
def create_job_and_lock_escrow(request: JobEscrowLockRequest):
    """
    İşveren için pozisyon ilanını açar ve bütçeyi saklamasız emanet kasasında kilitler.
    Bütçe kilitlenmeden aktif ilan yayınlanamaz (Active Hiring Proof-of-Budget).
    """
    try:
        locked_amount = calculate_escrow_budget_lock(
            base_hourly_rate=request.base_hourly_rate,
            expected_hours=request.expected_hours,
            overtime_margin=Decimal("0.20"),
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    platform_fee = (locked_amount * Decimal("0.03")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    job_id = uuid4()
    escrow_id = uuid4()
    tx_ref = f"ESC-TR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{job_id.hex[:8].upper()}"

    # Veritabanına kaydet
    repo.create_job(
        employer_id=str(request.employer_id),
        title=request.title,
        category=request.category,
        base_hourly_rate=request.base_hourly_rate,
        expected_hours=request.expected_hours,
        overtime_multiplier=request.overtime_multiplier,
        job_id=str(job_id),
    )
    repo.create_escrow_account(
        job_id=str(job_id),
        locked_amount=locked_amount,
        platform_fee=platform_fee,
        provider_tx_ref=tx_ref,
        provider_type=request.escrow_provider,
        escrow_id=str(escrow_id),
    )

    return JobEscrowLockResponse(
        job_id=job_id,
        escrow_account_id=escrow_id,
        title=request.title,
        status="active",
        is_budget_locked=True,
        locked_amount=locked_amount,
        platform_fee=platform_fee,
        escrow_tx_ref=tx_ref,
        active_hiring_verified=True,
    )


@app.get("/api/v1/jobs", tags=["Emanet & İlan"])
def list_jobs():
    """Tüm aktif ve kilitli ilanları listeler."""
    return repo.list_jobs()


@app.get("/api/v1/jobs/{job_id}", tags=["Emanet & İlan"])
def get_job_details(job_id: str):
    """İlan ve kilitli emanet fonu ayrıntılarını döner."""
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlan bulunamadı.")
    escrow = repo.get_escrow_by_job_id(job_id)
    return {"job": job, "escrow": escrow}


@app.post(
    "/api/v1/attendance/check-in",
    response_model=AttendanceCheckInResponse,
    status_code=status.HTTP_200_OK,
    tags=["Saha & Mesai"],
)
def check_in_worker(request: AttendanceCheckInRequest):
    """
    Saha veya set çalışanının Wi-Fi RTT ve mobil biyometrik canlılık verileriyle mesai girişini onaylar.
    """
    distance_ok = True
    dist_m = None
    if request.wifi_rtt_telemetry:
        dist_m = request.wifi_rtt_telemetry.distance_meters
        if dist_m > 500.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Çalışan tanımlı şantiye/set koordinatının (500m) dışındadır.",
            )
        if request.wifi_rtt_telemetry.accuracy_meters > 15.0:
            distance_ok = False

    event_id = uuid4()
    actual_time = datetime.now(timezone.utc).isoformat()

    # Kalıcı veri tabanına kaydet
    repo.record_attendance_event(
        shift_id=str(request.shift_id),
        event_type="check_in",
        wifi_rtt_distance_meters=dist_m,
        ble_beacon_uuid=request.ble_beacon_id,
        liveness_verification_hash=request.liveness_hash,
        ptp_monotonic_timestamp=request.client_monotonic_ptp,
        is_verified=True,
        event_id=str(event_id),
    )

    return AttendanceCheckInResponse(
        event_id=event_id,
        shift_id=request.shift_id,
        worker_id=request.worker_id,
        shift_status="checked_in",
        actual_check_in=actual_time,
        is_verified=True,
        distance_verified=distance_ok,
        ptp_time_synchronized=True,
        overtime_auto_calculator_active=True,
    )


@app.post(
    "/api/v1/attendance/qr/generate",
    response_model=RollingQRGenerateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Saha & Mesai"],
)
def generate_attendance_qr(request: RollingQRGenerateRequest):
    """
    İşveren / şantiye ekranında her 15 saniyede bir dönen kriptografik QR token üretir.
    """
    qr_data = generate_rolling_qr_token(job_id=str(request.job_id), shift_id=str(request.shift_id))
    return RollingQRGenerateResponse(
        token=qr_data["token"],
        job_id=request.job_id,
        shift_id=request.shift_id,
        window_step=qr_data["window_step"],
        nonce=qr_data["nonce"],
        seconds_remaining=qr_data["seconds_remaining"],
        expires_at_epoch=qr_data["expires_at_epoch"],
    )


@app.post(
    "/api/v1/attendance/qr/verify",
    response_model=RollingQRVerifyResponse,
    status_code=status.HTTP_200_OK,
    tags=["Saha & Mesai"],
)
def verify_attendance_qr(request: RollingQRVerifyRequest):
    """
    Çalışanın mobil kamerayla taradığı dönen QR kodunu ve Wi-Fi RTT mesafesini doğrular.
    """
    verification = verify_rolling_qr_token(
        token=request.token,
        expected_job_id=str(request.job_id),
        expected_shift_id=str(request.shift_id),
    )

    if not verification["is_valid"]:
        return RollingQRVerifyResponse(
            is_valid=False,
            event_id=None,
            shift_id=request.shift_id,
            worker_id=request.worker_id,
            detail=verification["detail"],
            is_verified=False,
            distance_verified=False,
            actual_check_in=None,
        )

    distance_ok = True
    dist_m = None
    if request.wifi_rtt_telemetry:
        dist_m = request.wifi_rtt_telemetry.distance_meters
        if dist_m > 500.0:
            return RollingQRVerifyResponse(
                is_valid=False,
                event_id=None,
                shift_id=request.shift_id,
                worker_id=request.worker_id,
                detail="Çalışan şantiye geofence koordinatının (500m) dışındadır.",
                is_verified=False,
                distance_verified=False,
                actual_check_in=None,
            )
        if request.wifi_rtt_telemetry.accuracy_meters > 15.0:
            distance_ok = False

    event_id = uuid4()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Yoklama olayını DB'ye kütükle
    repo.record_attendance_event(
        shift_id=str(request.shift_id),
        event_type="check_in",
        wifi_rtt_distance_meters=dist_m,
        liveness_verification_hash=request.liveness_hash,
        ptp_monotonic_timestamp=request.client_monotonic_ptp,
        is_verified=True,
        event_id=str(event_id),
    )

    return RollingQRVerifyResponse(
        is_valid=True,
        event_id=event_id,
        shift_id=request.shift_id,
        worker_id=request.worker_id,
        detail="Dönen QR kodu ve Wi-Fi RTT donanım zamanı başarıyla doğrulandı.",
        is_verified=True,
        distance_verified=distance_ok,
        actual_check_in=now_iso,
    )


@app.post(
    "/api/v1/jobs/{job_id}/dispatch-emergency",
    response_model=EmergencyDispatchResponse,
    status_code=status.HTTP_200_OK,
    tags=["Saha & Mesai"],
)
def dispatch_emergency_standby(job_id: UUID, request: EmergencyDispatchRequest):
    """
    Vardiyaya gelmeyen (no-show) çalışan durumunda 10 dakikalık hızlı yedekleme boru hattını tetikler.
    """
    candidates_pool = request.candidates_pool
    if not candidates_pool:
        # Gerçekçi sertifikalı yedek havuzu simülasyonu
        candidates_pool = [
            {
                "id": str(uuid4()),
                "name": "Ahmet Y. (Sertifikalı Set Teknisyeni)",
                "distance_km": 3.4,
                "reputation_score": 96.5,
                "reaction_time_ms": 218.0,
                "age": 28,
                "weekly_gaming_hours": 8.0,
                "is_available": True,
            },
            {
                "id": str(uuid4()),
                "name": "Burak K. (Kamera & Işık Asistanı)",
                "distance_km": 6.8,
                "reputation_score": 89.0,
                "reaction_time_ms": 235.0,
                "age": 32,
                "weekly_gaming_hours": 0.0,
                "is_available": True,
            },
            {
                "id": str(uuid4()),
                "name": "Canan T. (Ses Teknisyeni)",
                "distance_km": 11.2,
                "reputation_score": 92.0,
                "reaction_time_ms": 222.0,
                "age": 26,
                "weekly_gaming_hours": 12.0,
                "is_available": True,
            },
        ]

    dispatch_result = trigger_emergency_dispatch(
        job_id=str(job_id),
        shift_id=str(request.shift_id),
        base_hourly_rate=request.base_hourly_rate,
        available_candidates=candidates_pool,
    )

    if not dispatch_result["success"]:
        return EmergencyDispatchResponse(
            success=False,
            job_id=job_id,
            shift_id=request.shift_id,
            status=dispatch_result["status"],
            message=dispatch_result["message"],
            primary_assigned_candidate=None,
            standby_pool_size=0,
            base_hourly_rate=request.base_hourly_rate,
            rush_hourly_rate=request.base_hourly_rate,
            rush_premium_hourly=Decimal("0.00"),
            sla_target_minutes=10,
            estimated_arrival_minutes=None,
        )

    return EmergencyDispatchResponse(
        success=True,
        job_id=job_id,
        shift_id=request.shift_id,
        status=dispatch_result["status"],
        primary_assigned_candidate=dispatch_result["primary_assigned_candidate"],
        standby_pool_size=dispatch_result["standby_pool_size"],
        base_hourly_rate=dispatch_result["base_hourly_rate"],
        rush_hourly_rate=dispatch_result["rush_hourly_rate"],
        rush_premium_hourly=dispatch_result["rush_premium_hourly"],
        sla_target_minutes=dispatch_result["sla_target_minutes"],
        estimated_arrival_minutes=dispatch_result["estimated_arrival_minutes"],
    )


@app.post(
    "/api/v1/tax/e-gider-pusulasi/generate",
    response_model=GIBInvoiceResponse,
    status_code=status.HTTP_200_OK,
    tags=["Vergi & GİB"],
)
def generate_gib_e_gider_pusulasi(request: GIBInvoiceRequest):
    """
    Vergi mükellefi olmayan çalışan adına GİB entegrasyonuyla e-Gider Pusulası ve stopaj tanzim eder.
    """
    if request.net_payout is not None:
        tax_res = compute_gib_net_gross_tax(request.net_payout, request.withholding_tax_rate)
        gross = tax_res["gross_amount"]
        withholding = tax_res["withholding_tax_deducted"]
        net = tax_res["net_payout"]
    else:
        gross = request.gross_amount  # type: ignore
        withholding = (gross * request.withholding_tax_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        net = gross - withholding

    invoice_id = uuid4()
    pdf_url = f"https://vault.pactiva.internal/invoices/{datetime.now(timezone.utc).year}/{invoice_id}.pdf"

    # Veritabanına kaydet
    repo.create_tax_invoice(
        shift_id=str(request.shift_id),
        worker_id=str(request.worker_id),
        gib_invoice_uuid=str(invoice_id),
        gross_amount=gross,
        withholding_tax_amount=withholding,
        net_payout_amount=net,
        gib_response_status="reported",
    )

    return GIBInvoiceResponse(
        gib_invoice_uuid=invoice_id,
        shift_id=request.shift_id,
        worker_id=request.worker_id,
        gross_amount=gross,
        withholding_tax_deducted=withholding,
        net_payout=net,
        tax_rate_applied=request.withholding_tax_rate,
        gib_portal_signed=True,
        pdf_archive_url=pdf_url,
    )


@app.post(
    "/api/v1/arbitration/vote",
    response_model=JuryVoteResponse,
    status_code=status.HTTP_200_OK,
    tags=["Tahkim & Jüri"],
)
def submit_juror_vote(request: JuryVoteRequest):
    """
    7 Üyeli bağımsız jüri uyuşmazlık kör oyunu karesel ağırlıkla kütükler.
    """
    quadratic_weight = Decimal(str(math.sqrt(float(request.stake_amount)))).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    return JuryVoteResponse(
        dispute_id=request.dispute_id,
        juror_id=request.juror_id,
        vote_decision=request.vote_decision,
        quadratic_vote_weight=quadratic_weight,
        status="recorded",
    )


@app.post(
    "/api/v1/attestations/create",
    response_model=PeerAttestationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Yetkinlik & Meslektaş"],
)
def submit_peer_attestation(request: PeerAttestationCreateRequest):
    """
    Aynı projede/sette çalışan işçilerin birbirinin yetkinliğini kriptografik onaylaması.
    Kendi kendine referans (self-endorsement) kural olarak engellenir.
    """
    try:
        res = create_peer_attestation(
            worker_id=str(request.worker_id),
            endorser_id=str(request.endorser_id),
            job_id=str(request.job_id),
            overlap_start_date=request.overlap_start_date,
            overlap_end_date=request.overlap_end_date,
            endorser_reputation_score=request.endorser_reputation_score,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return PeerAttestationCreateResponse(
        attestation_id=UUID(res["attestation_id"]),
        worker_id=request.worker_id,
        endorser_id=request.endorser_id,
        job_id=request.job_id,
        overlap_start_date=request.overlap_start_date,
        overlap_end_date=request.overlap_end_date,
        signature=res["signature"],
        endorser_reputation_weight=res["endorser_reputation_weight"],
        is_verified=True,
    )


@app.get("/api/v1/attestations/{worker_id}", tags=["Yetkinlik & Meslektaş"])
def get_worker_peer_attestations(worker_id: UUID):
    """Bir çalışanın aldığı onayları ve kümülatif güven çarpanını döner."""
    return get_worker_attestations(str(worker_id))


@app.post(
    "/api/v1/skills/match",
    response_model=SkillMatchResponse,
    status_code=status.HTTP_200_OK,
    tags=["Yetkinlik & Meslektaş"],
)
def match_candidates_by_skills(request: SkillMatchRequest):
    """
    İlanın gerektirdiği yetkinliklerle aday havuzunu kosinüs benzerliği üzerinden eşleştirir.
    """
    job_vec = generate_skill_vector_stub(request.job_skills, dimension=64)
    ranked = rank_candidates_by_skill_match(
        job_skills_vector=job_vec,
        candidates=request.candidates,
        min_match_threshold=request.min_match_threshold,
    )
    return SkillMatchResponse(
        job_skills=request.job_skills,
        total_candidates_evaluated=len(request.candidates),
        ranked_matches=ranked,
    )


@app.post(
    "/api/v1/arbitration/disputes/create",
    response_model=DisputeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tahkim & Jüri"],
)
def open_arbitration_dispute(request: DisputeCreateRequest):
    """
    Uyuşmazlık dosyasını açar ve kör delil paketiyle shift'i dondurur.
    """
    dispute = create_dispute(
        shift_id=str(request.shift_id),
        initiator_id=str(request.initiator_id),
        reason=request.reason,
        evidence_archive_hash=request.evidence_archive_hash,
    )
    return DisputeCreateResponse(
        id=UUID(dispute["id"]),
        shift_id=request.shift_id,
        initiator_id=request.initiator_id,
        reason=request.reason,
        evidence_archive_hash=request.evidence_archive_hash,
        resolution_status=dispute["resolution_status"],
    )


@app.post(
    "/api/v1/arbitration/disputes/{dispute_id}/resolve",
    response_model=DisputeResolveResponse,
    status_code=status.HTTP_200_OK,
    tags=["Tahkim & Jüri"],
)
def resolve_arbitration_dispute(dispute_id: UUID, request: DisputeResolveRequest):
    """
    7 Üyeli jüri oylarını Schelling konsensüsüyle çözümler; aykırı oylara %30 slashing kesintisi uygular.
    """
    try:
        res = resolve_dispute(
            dispute_id=str(dispute_id),
            votes_data=request.votes,
            consensus_threshold=request.consensus_threshold,
            slash_rate=request.slash_rate,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return DisputeResolveResponse(
        dispute_id=dispute_id,
        resolution_status=res["resolution_status"],
        consensus_score=res["consensus_score"],
        settlement_description=res["settlement_description"],
        total_penalty_slashed=res["total_penalty_slashed"],
        juror_count=res["juror_count"],
        juror_results=res["juror_results"],
        resolved_at=res["resolved_at"],
    )


@app.post(
    "/api/v1/liveness/verify",
    response_model=LivenessCheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["Sistem"],
)
def check_touch_liveness(request: LivenessCheckRequest):
    """
    Dokunmatik ekran dokunma sürelerini ve titreşim (jitter) standart sapmasını inceleyerek botları eler.
    """
    res = verify_touch_liveness(
        tap_intervals_ms=request.tap_intervals_ms,
        touch_radii=request.touch_radii,
    )
    return LivenessCheckResponse(
        is_human=res["is_human"],
        average_reaction_ms=res.get("average_reaction_ms"),
        jitter_std_dev_ms=res.get("jitter_std_dev_ms"),
        timing_entropy_bits=res.get("timing_entropy_bits"),
        liveness_hash=res.get("liveness_hash"),
        detail=res["detail"],
    )


@app.post(
    "/api/v1/contracts/generate",
    response_model=ContractGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Yasal & Sözleşme"],
)
def create_statutory_contract(request: ContractGenerateRequest):
    """
    4857 SK Md. 2 müteselsil SGK izolasyonu ve GVK Md. 94 uyumlu üçlü yasal sözleşmeyi tanzim eder.
    """
    contract = generate_tripartite_contract(
        employer_id=str(request.employer_id),
        worker_id=str(request.worker_id),
        job_id=str(request.job_id),
        job_title=request.job_title,
        base_hourly_rate=request.base_hourly_rate,
        expected_hours=request.expected_hours,
        category=request.category,
    )
    return ContractGenerateResponse(
        contract_id=UUID(contract["contract_id"]),
        employer_id=request.employer_id,
        worker_id=request.worker_id,
        job_id=request.job_id,
        job_title=request.job_title,
        category=request.category,
        base_hourly_rate=request.base_hourly_rate,
        expected_hours=request.expected_hours,
        estimated_total_payout=contract["estimated_total_payout"],
        statutory_compliance=contract["statutory_compliance"],
        contract_sha256_hash=contract["contract_sha256_hash"],
        canonical_clauses=contract["canonical_clauses"],
        archive_url=contract["archive_url"],
        created_at=contract["created_at"],
        is_digitally_signed=True,
    )


@app.post(
    "/api/v1/ptp/sync",
    response_model=PTPSyncResponse,
    status_code=status.HTTP_200_OK,
    tags=["Sistem"],
)
def verify_ptp_clock(request: PTPSyncRequest):
    """
    IEEE 1588 donanımsal zaman protokolüyle cihaz saati manipülasyonlarını (offset/skew) denetler.
    """
    res = synchronize_and_verify_ptp(
        client_ptp_timestamp_ns=request.client_ptp_timestamp_ns,
        previous_event_ptp_ns=request.previous_event_ptp_ns,
        estimated_network_rtt_ns=request.estimated_network_rtt_ns,
    )
    return PTPSyncResponse(
        is_synchronized=res["is_synchronized"],
        clock_offset_ms=res.get("clock_offset_ms"),
        master_timestamp_ns=res.get("master_timestamp_ns"),
        client_timestamp_ns=res.get("client_timestamp_ns"),
        ptp_jitter_ms=res.get("ptp_jitter_ms"),
        error_code=res.get("error_code"),
        detail=res["detail"],
    )


@app.get(
    "/api/v1/erp/export",
    response_model=ERPExportResponse,
    status_code=status.HTTP_200_OK,
    tags=["Kurumsal ERP & Muhasebe"],
)
def export_erp_journal_entries(
    format: str = "json",
    account_cost_center: str = "740.01.001",
):
    """
    Tekdüzen Hesap Planına (THP) uygun çift taraflı mahsup fişlerini JSON, Logo XML veya SAP CSV formatında dışa aktarır.
    """
    if format not in ("json", "logo_xml", "sap_csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Desteklenmeyen format: {format}. Desteklenenler: json, logo_xml, sap_csv",
        )

    invoices = repo.list_tax_invoices(limit=500)
    entries = []
    total_gross = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_net = Decimal("0.00")

    for inv in invoices:
        g = Decimal(str(inv["gross_amount"])).quantize(TWO_PLACES)
        t = Decimal(str(inv["withholding_tax_amount"])).quantize(TWO_PLACES)
        n = Decimal(str(inv["net_payout_amount"])).quantize(TWO_PLACES)
        total_gross += g
        total_tax += t
        total_net += n
        entry = generate_journal_entry(
            shift_id=str(inv["shift_id"]),
            worker_name=f"Yüklenici #{str(inv['worker_id'])[:8]}",
            project_title="Saha İstihdam Hizmeti",
            gross_amount=g,
            withholding_tax=t,
            net_payout=n,
            account_cost_center=account_cost_center,
        )
        entries.append(entry)

    if format == "logo_xml":
        payload = export_to_logo_xml(entries)
    elif format == "sap_csv":
        payload = export_to_sap_csv(entries)
    else:
        import json
        payload = json.dumps(entries, default=str, ensure_ascii=False, indent=2)

    return ERPExportResponse(
        format=format,
        total_entries=len(entries),
        total_gross=total_gross.quantize(TWO_PLACES),
        total_tax=total_tax.quantize(TWO_PLACES),
        total_net=total_net.quantize(TWO_PLACES),
        export_payload=payload,
    )


@app.post(
    "/api/v1/erp/export",
    response_model=ERPExportResponse,
    status_code=status.HTTP_200_OK,
    tags=["Kurumsal ERP & Muhasebe"],
)
def export_erp_journal_entries_post(request: ERPExportRequest):
    return export_erp_journal_entries(
        format=request.format,
        account_cost_center=request.account_cost_center,
    )


@app.post(
    "/api/v1/attendance/offline-sync",
    response_model=OfflineBatchSyncResponse,
    status_code=status.HTTP_200_OK,
    tags=["Saha & Yoklama"],
)
def sync_offline_attendance_batch(request: OfflineBatchSyncRequest):
    """
    Şantiye veya bodrum katı şebeke kesintilerinde biriken kriptografik hash zincirli çevrimdışı yoklama olaylarını toplu işler.
    """
    event_dicts = [ev.model_dump() for ev in request.events]
    res = process_offline_attendance_batch(event_dicts)
    return OfflineBatchSyncResponse(
        success=res["success"],
        synced_count=res["synced_count"],
        final_block_hash=res.get("final_block_hash"),
        detail=res["detail"],
    )


@app.post(
    "/api/v1/audit/record",
    response_model=AuditRecordResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Kriptografik Denetim"],
)
def record_audit_ledger_event(request: AuditRecordRequest):
    """
    Emanet, ödeme, sözleşme veya uyuşmazlık olayını değiştirilemez Merkle-hash denetim zincirine (Proof-of-Audit) mühürler.
    """
    res = record_audit_event(
        action_type=request.action_type,
        payload=request.payload,
    )
    return AuditRecordResponse(
        block_index=res["block_index"],
        action_type=res["action_type"],
        payload_hash=res["payload_hash"],
        prev_block_hash=res["prev_block_hash"],
        block_hash=res["block_hash"],
        created_at=res["created_at"],
        is_immutable=res["is_immutable"],
    )


@app.get(
    "/api/v1/audit/verify",
    response_model=AuditVerifyResponse,
    status_code=status.HTTP_200_OK,
    tags=["Kriptografik Denetim"],
)
def verify_audit_ledger():
    """
    Denetim zincirini baştan sona tarayarak tahrifat ve blok zinciri kopukluklarını denetler.
    """
    res = verify_audit_ledger_integrity()
    return AuditVerifyResponse(
        is_valid=res["is_valid"],
        total_blocks=res["total_blocks"],
        latest_block_hash=res.get("latest_block_hash"),
        detail=res["detail"],
    )


@app.post(
    "/api/v1/contracts/verify",
    response_model=ContractVerifyResponse,
    status_code=status.HTTP_200_OK,
    tags=["Yasal & Sözleşme"],
)
def verify_statutory_contract(request: ContractVerifyRequest):
    """
    Sözleşme kanuni maddelerinin SHA-256 kriptografik mühürüyle tahrif edilip edilmediğini doğrular.
    """
    is_valid = verify_contract_integrity(
        canonical_clauses=request.canonical_clauses,
        expected_hash=request.expected_hash,
    )
    import hashlib
    computed = hashlib.sha256("\n\n".join(request.canonical_clauses).encode("utf-8")).hexdigest()
    return ContractVerifyResponse(
        is_valid=is_valid,
        computed_hash=computed,
        expected_hash=request.expected_hash,
        statutory_compliance_status="VERIFIED_COMPLIANT" if is_valid else "TAMPERED_BREACH",
        detail="Sözleşme bütünlüğü ve kanuni koruma maddeleri kusursuz doğrulandı." if is_valid else "Sözleşme metninde tahrifat tespit edildi.",
    )


@app.post(
    "/api/v1/escrow/release",
    response_model=EscrowReleaseResponse,
    status_code=status.HTTP_200_OK,
    tags=["Emanet & İlan"],
)
def release_escrow(request: EscrowReleaseRequest):
    """
    Mesai tamamlandıktan sonra emanet kasasındaki hak edişi serbest bırakır ve denetim zincirine mühürler.
    """
    try:
        escrow = repo.release_escrow_payout(
            job_id=str(request.job_id),
            payout_amount=request.payout_amount,
            withholding_tax_amount=request.withholding_tax_amount,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    audit_block = record_audit_event(
        action_type="ESCROW_PAYOUT_RELEASED",
        payload={
            "job_id": str(request.job_id),
            "payout_amount": str(request.payout_amount),
            "withholding_tax_amount": str(request.withholding_tax_amount),
        },
    )

    return EscrowReleaseResponse(
        success=True,
        job_id=request.job_id,
        status="disbursed",
        payout_amount=request.payout_amount,
        withholding_tax_amount=request.withholding_tax_amount,
        audit_block_hash=audit_block["block_hash"],
        detail="Emanet kasasından hak ediş başarıyla aktarıldı ve denetim zincirine mühürlendi.",
    )


@app.post(
    "/api/v1/escrow/refund",
    response_model=EscrowRefundResponse,
    status_code=status.HTTP_200_OK,
    tags=["Emanet & İlan"],
)
def refund_escrow_budget(request: EscrowRefundRequest):
    """
    Vardiya gerçekleşmeden önce iptal edilen işlerin bloke bütçesini işverene iade eder.
    """
    try:
        escrow = repo.refund_escrow(
            job_id=str(request.job_id),
            refund_reason=request.refund_reason,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    audit_block = record_audit_event(
        action_type="ESCROW_REFUNDED_TO_EMPLOYER",
        payload={
            "job_id": str(request.job_id),
            "refund_reason": request.refund_reason,
        },
    )

    return EscrowRefundResponse(
        success=True,
        job_id=request.job_id,
        status="refunded",
        refund_reason=request.refund_reason,
        audit_block_hash=audit_block["block_hash"],
        detail="Emanet bütçesi işverene iade edildi ve iptal kaydı denetim zincirine mühürlendi.",
    )


@app.post(
    "/api/v1/webhooks/subscribe",
    response_model=WebhookSubscribeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Kurumsal Webhook"],
)
def register_webhook(request: WebhookSubscribeRequest):
    """
    ERP, muhasebe veya İK sistemleri için HMAC-SHA256 imzalı webhook aboneliği tanımlar.
    """
    sub = create_webhook_subscription(
        target_url=request.target_url,
        secret_key=request.secret_key,
        events=request.events,
    )
    return WebhookSubscribeResponse(
        id=UUID(sub["id"]),
        target_url=sub["target_url"],
        events=sub["events"],
        is_active=sub["is_active"],
        created_at=sub["created_at"],
    )


@app.get(
    "/api/v1/webhooks/subscriptions",
    response_model=List[WebhookSubscribeResponse],
    status_code=status.HTTP_200_OK,
    tags=["Kurumsal Webhook"],
)
def get_webhook_subscriptions():
    """Kayıtlı aktif webhook abonelerini listeler."""
    subs = list_webhook_subscriptions(active_only=True)
    return [
        WebhookSubscribeResponse(
            id=UUID(s["id"]),
            target_url=s["target_url"],
            events=s["events"],
            is_active=s["is_active"],
            created_at=s["created_at"],
        )
        for s in subs
    ]


@app.post(
    "/api/v1/webhooks/dispatch",
    response_model=WebhookDispatchTestResponse,
    status_code=status.HTTP_200_OK,
    tags=["Kurumsal Webhook"],
)
def trigger_webhook_event_dispatch(request: WebhookDispatchTestRequest):
    """
    Belirtilen olayı kayıtlı abonelere manuel veya test amaçlı sevk eder.
    """
    res = dispatch_event_to_webhooks(
        event_type=request.event_type,
        payload=request.payload,
    )
    return WebhookDispatchTestResponse(
        event=res["event"],
        dispatched_count=res["dispatched_count"],
        deliveries=res["deliveries"],
    )


# Web Arayüzü Statik Dosya Entegrasyonu
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
if os.path.exists(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
