"""
Pactiva — 15-Saniyelik Kriptografik Dönen QR ve Yoklama Motoru (pactiva_core/qr_engine.py)
Hayalet işçi (Ghost worker) ve uzaktan sahte check-in sahtekarlığını önleyen donanımsal zaman pencereli doğrulama.
"""

import hashlib
import hmac
import os
import secrets
import time
from typing import Any, Dict, Optional, Set

QR_VALIDITY_WINDOW_SECONDS: int = 15
DEFAULT_SECRET: str = os.environ.get("PACTIVA_QR_SECRET", "pactiva_enterprise_dynamic_qr_signing_key_2026")

# Replay saldırılarını önlemek için kullanılan tek kullanımlık nonce kaydı
_USED_NONCE_CACHE: Set[str] = set()
_LAST_CACHE_CLEANUP: float = time.time()


def _cleanup_nonce_cache() -> None:
    global _USED_NONCE_CACHE, _LAST_CACHE_CLEANUP
    # Her 5 dakikada bir önbellek temizlenir
    if time.time() - _LAST_CACHE_CLEANUP > 300:
        _USED_NONCE_CACHE.clear()
        _LAST_CACHE_CLEANUP = time.time()


def generate_rolling_qr_token(
    job_id: str,
    shift_id: str,
    timestamp_sec: Optional[int] = None,
    secret_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    İşveren/şantiye ekranında her 15 saniyede bir dönen kriptografik QR tokeni üretir.
    """
    now = int(time.time()) if timestamp_sec is None else timestamp_sec
    window_step = now // QR_VALIDITY_WINDOW_SECONDS
    seconds_remaining = QR_VALIDITY_WINDOW_SECONDS - (now % QR_VALIDITY_WINDOW_SECONDS)
    key = (secret_key or DEFAULT_SECRET).encode("utf-8")
    nonce = secrets.token_hex(8)

    message = f"{job_id}:{shift_id}:{window_step}:{nonce}"
    signature = hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()[:24]

    token_string = f"PACTIVA:{job_id}:{shift_id}:{window_step}:{nonce}:{signature}"

    return {
        "token": token_string,
        "job_id": job_id,
        "shift_id": shift_id,
        "window_step": window_step,
        "nonce": nonce,
        "seconds_remaining": seconds_remaining,
        "expires_at_epoch": (window_step + 1) * QR_VALIDITY_WINDOW_SECONDS,
    }


def verify_rolling_qr_token(
    token: str,
    expected_job_id: str,
    expected_shift_id: str,
    current_timestamp_sec: Optional[int] = None,
    secret_key: Optional[str] = None,
    allowed_window_drift: int = 1,
) -> Dict[str, Any]:
    """
    Çalışanın taradığı QR tokenini doğrular.
    Zaman penceresi drift'i (±15s gecikme toleransı) ve tekrar oynatma (replay attack) kontrollerini uygular.
    """
    _cleanup_nonce_cache()

    parts = token.split(":")
    if len(parts) != 6 or parts[0] != "PACTIVA":
        return {
            "is_valid": False,
            "error_code": "INVALID_FORMAT",
            "detail": "QR token formatı geçersiz veya Pactiva protokolüne uygun değil.",
        }

    _, token_job_id, token_shift_id, token_window_str, nonce, token_sig = parts

    if token_job_id != str(expected_job_id):
        return {
            "is_valid": False,
            "error_code": "JOB_MISMATCH",
            "detail": "QR tokeni bu ilana ait değil.",
        }

    if token_shift_id != str(expected_shift_id):
        return {
            "is_valid": False,
            "error_code": "SHIFT_MISMATCH",
            "detail": "QR tokeni bu vardiyaya ait değil.",
        }

    try:
        token_window = int(token_window_str)
    except ValueError:
        return {
            "is_valid": False,
            "error_code": "MALFORMED_WINDOW",
            "detail": "Zaman penceresi sayısı geçersiz.",
        }

    now = int(time.time()) if current_timestamp_sec is None else current_timestamp_sec
    current_window = now // QR_VALIDITY_WINDOW_SECONDS

    # Zaman kayması toleransı: [current - drift, current + drift]
    if abs(current_window - token_window) > allowed_window_drift:
        return {
            "is_valid": False,
            "error_code": "TOKEN_EXPIRED",
            "detail": f"QR kodun süresi doldu (Geçerlilik penceresi: {QR_VALIDITY_WINDOW_SECONDS}s). Lütfen güncel kodu tarayın.",
        }

    # Replay saldırı kontrolü: Aynı nonce ikinci kez kullanılamaz
    nonce_cache_key = f"{token_job_id}:{token_shift_id}:{token_window}:{nonce}"
    if nonce_cache_key in _USED_NONCE_CACHE:
        return {
            "is_valid": False,
            "error_code": "REPLAY_DETECTED",
            "detail": "Bu QR token daha önce kullanıldı. Ekran görüntüsüyle mükerrer giriş yapılamaz.",
        }

    # HMAC imza doğrulaması
    key = (secret_key or DEFAULT_SECRET).encode("utf-8")
    expected_message = f"{token_job_id}:{token_shift_id}:{token_window}:{nonce}"
    expected_signature = hmac.new(key, expected_message.encode("utf-8"), hashlib.sha256).hexdigest()[:24]

    if not hmac.compare_digest(expected_signature, token_sig):
        return {
            "is_valid": False,
            "error_code": "SIGNATURE_MISMATCH",
            "detail": "Kriptografik imza sahte veya manipüle edilmiş.",
        }

    # Geçerli işlem: Nonce önbelleğe alınır
    _USED_NONCE_CACHE.add(nonce_cache_key)

    return {
        "is_valid": True,
        "token_window": token_window,
        "current_window": current_window,
        "detail": "15 saniyelik dönen QR kodu ve canlılık başarıyla doğrulandı.",
    }
