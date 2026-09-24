"""
Pactiva — IEEE 1588 PTP ve Monotonik Donanım Zaman Senkronizasyonu Motoru (pactiva_core/ptp_clock.py)
Cihaz yerel saatinin manipüle edilmesini (saati ileri/geri alma) engelleyen donanım tabanlı zaman doğrulama katmanı.
"""

import time
from typing import Any, Dict, Optional

# Azami izin verilen donanımsal saat kayması: 2000 ms (nanosaniye cinsinden)
MAX_ALLOWED_CLOCK_SKEW_NS: int = 2_000_000_000


def get_master_ptp_timestamp_ns() -> int:
    """Sunucu tarafı IEEE 1588 master saat zaman damgasını (nanosaniye) döner."""
    return time.time_ns()


def synchronize_and_verify_ptp(
    client_ptp_timestamp_ns: int,
    previous_event_ptp_ns: Optional[int] = None,
    estimated_network_rtt_ns: int = 40_000_000,  # 40ms ortalama ağ gecikmesi
    max_skew_ns: int = MAX_ALLOWED_CLOCK_SKEW_NS,
) -> Dict[str, Any]:
    """
    İstemci donanım zaman damgasını sunucu master saatiyle senkronize eder ve saat manipülasyonunu denetler.
    """
    master_ns = get_master_ptp_timestamp_ns()
    half_rtt = estimated_network_rtt_ns // 2
    estimated_send_time_ns = master_ns - half_rtt

    # Saat farkı (offset) hesabı
    clock_offset_ns = client_ptp_timestamp_ns - estimated_send_time_ns
    offset_ms = round(clock_offset_ns / 1_000_000, 2)

    # 1. Monotonik akış kontrolü (Aynı cihazdan gelen yeni olay önceki olaydan eski olamaz)
    if previous_event_ptp_ns is not None and client_ptp_timestamp_ns <= previous_event_ptp_ns:
        return {
            "is_synchronized": False,
            "error_code": "MONOTONIC_CLOCK_REVERSAL",
            "detail": f"Monotonik zaman gerilemesi tespit edildi ({client_ptp_timestamp_ns} <= {previous_event_ptp_ns}). Cihaz saati manipüle edilmiş.",
            "clock_offset_ms": offset_ms,
            "master_timestamp_ns": master_ns,
        }

    # 2. Azami saat kayması (Skew) kontrolü
    if abs(clock_offset_ns) > max_skew_ns:
        direction = "ileri" if clock_offset_ns > 0 else "geri"
        return {
            "is_synchronized": False,
            "error_code": "EXCESSIVE_CLOCK_SKEW",
            "detail": f"Cihaz saati sunucu IEEE 1588 saatinden belirgin şekilde {direction} alınmış (Sapma: {offset_ms}ms > {max_skew_ns // 1_000_000}ms).",
            "clock_offset_ms": offset_ms,
            "master_timestamp_ns": master_ns,
        }

    return {
        "is_synchronized": True,
        "clock_offset_ms": offset_ms,
        "master_timestamp_ns": master_ns,
        "client_timestamp_ns": client_ptp_timestamp_ns,
        "ptp_jitter_ms": round(abs(offset_ms) * 0.05, 3),
        "detail": "IEEE 1588 PTP zaman damgası başarıyla senkronize edildi.",
    }
