"""
Pactiva — Çevrimdışı (Offline-First) Şantiye Senkronizasyonu ve Kriptografik Kuyruk Motoru (pactiva_core/offline_sync.py)
Şantiye ve stüdyo bodrum katlarında şebeke kesintilerinde yerel hash-chain bütünlüğüyle toplu yoklama aktarımı.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pactiva_core.database import get_db
from pactiva_core.repository import PactivaRepository


def compute_event_chain_hash(
    prev_hash: str,
    shift_id: str,
    worker_id: str,
    ptp_monotonic_timestamp_ns: int,
    wifi_rtt_distance_meters: float,
    event_type: str,
) -> str:
    """Olayın değiştirilemez Merkle-chain özetini hesaplar."""
    payload = f"{prev_hash}:{shift_id}:{worker_id}:{ptp_monotonic_timestamp_ns}:{wifi_rtt_distance_meters:.2f}:{event_type}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def process_offline_attendance_batch(
    events: List[Dict[str, Any]],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Şebeke kesintisinde cihazda biriken yoklama ve PTP kanıt zincirini doğrular ve veritabanına işler.
    """
    if not events:
        return {
            "success": False,
            "synced_count": 0,
            "error_code": "EMPTY_BATCH",
            "detail": "Senkronize edilecek çevrimdışı olay bulunamadı.",
        }

    repo = PactivaRepository(db_path=db_path)
    verified_events = []
    prev_hash = "GENESIS_BLOCK_00000000000000000000000000000000000000000000000000000000"
    last_ptp = 0

    for idx, ev in enumerate(events):
        shift_id = str(ev["shift_id"])
        worker_id = str(ev["worker_id"])
        ptp_ns = int(ev["ptp_monotonic_timestamp_ns"])
        dist_m = float(ev["wifi_rtt_distance_meters"])
        event_type = ev.get("event_type", "check_in")
        claimed_hash = ev.get("event_hash")

        # 1. Monotonik zaman kontrolü
        if ptp_ns <= last_ptp and idx > 0:
            return {
                "success": False,
                "synced_count": 0,
                "error_code": "CHRONOLOGICAL_INVERSION",
                "detail": f"Olay #{idx} için monotonik zaman gerilemesi tespit edildi ({ptp_ns} <= {last_ptp}).",
            }
        last_ptp = ptp_ns

        # 2. Wi-Fi RTT Geofence kontrolü
        if dist_m > 500.0:
            return {
                "success": False,
                "synced_count": 0,
                "error_code": "GEOFENCE_BREACH",
                "detail": f"Olay #{idx} için Wi-Fi RTT mesafesi ({dist_m}m) 500m şantiye sınırını aşıyor.",
            }

        # 3. Kriptografik Hash-Chain kontrolü
        expected_hash = compute_event_chain_hash(
            prev_hash=prev_hash,
            shift_id=shift_id,
            worker_id=worker_id,
            ptp_monotonic_timestamp_ns=ptp_ns,
            wifi_rtt_distance_meters=dist_m,
            event_type=event_type,
        )

        if claimed_hash and claimed_hash != expected_hash:
            return {
                "success": False,
                "synced_count": 0,
                "error_code": "HASH_CHAIN_TAMPERED",
                "detail": f"Olay #{idx} zincirleme hash bütünlüğü uyuşmuyor. Çevrimdışı veri manipülasyonu tespit edildi.",
            }

        prev_hash = expected_hash
        verified_events.append({
            "shift_id": shift_id,
            "worker_id": worker_id,
            "event_type": event_type,
            "wifi_rtt_distance_meters": dist_m,
            "ptp_monotonic_timestamp": ptp_ns,
            "liveness_verification_hash": expected_hash,
            "is_verified": True,
        })

    # Veritabanına toplu yaz
    with get_db(db_path) as conn:
        for ve in verified_events:
            repo.record_attendance_event(
                shift_id=ve["shift_id"],
                event_type=ve["event_type"],
                wifi_rtt_distance_meters=ve["wifi_rtt_distance_meters"],
                liveness_verification_hash=ve["liveness_verification_hash"],
                ptp_monotonic_timestamp=ve["ptp_monotonic_timestamp"],
                is_verified=True,
            )

    return {
        "success": True,
        "synced_count": len(verified_events),
        "final_block_hash": prev_hash,
        "detail": f"{len(verified_events)} adet çevrimdışı yoklama ve PTP kanıtı başarıyla senkronize edildi.",
    }
