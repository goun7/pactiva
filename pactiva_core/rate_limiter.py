"""
Pactiva — İstemci Hız Sınırlayıcı ve DoS Kalkanı (pactiva_core/rate_limiter.py)
Dönen QR doğrulaması ve liveness kontrollerinde bot ve brute-force saldırılarını engeller.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List, Tuple


class SlidingWindowRateLimiter:
    """Kayan zaman pencereli (sliding-window) in-memory hız sınırlayıcı."""

    def __init__(self):
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(
        self,
        key: str,
        max_requests: int = 60,
        window_seconds: float = 60.0,
    ) -> Tuple[bool, int, float]:
        """
        İstek kotasını kontrol eder.
        Dönüş: (izin_verildi_mi, kalan_istek_sayısı, saniye_cinsinden_bekleme_süresi)
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            # Süresi dolmuş istekleri temizle
            timestamps = [t for t in self._requests[key] if t > cutoff]
            self._requests[key] = timestamps

            if len(timestamps) >= max_requests:
                earliest = timestamps[0]
                retry_after = max(0.1, round(window_seconds - (now - earliest), 2))
                return False, 0, retry_after

            # Yeni isteği kaydet
            self._requests[key].append(now)
            remaining = max_requests - len(self._requests[key])
            return True, remaining, 0.0

    def reset(self):
        """Test senaryoları için kotaları sıfırlar."""
        with self._lock:
            self._requests.clear()


# Global tekil nesne
global_rate_limiter = SlidingWindowRateLimiter()
