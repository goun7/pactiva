"""22-37-Pactiva qr_engine._cleanup_nonce_cache dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (modul global'leri + time.time() monkeypatch; network YASAK).

ORTAM-ANATOMI:
- _cleanup_nonce_cache(): global _USED_NONCE_CACHE, _LAST_CACHE_CLEANUP;
  if time.time() - _LAST_CACHE_CLEANUP > 300: .clear(); _LAST_CACHE_CLEANUP = time.time()
- _USED_NONCE_CACHE: Set[str] — replay-koruma nonce havuzu
"""
import sys
import time

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
import pactiva_core.qr_engine as q  # noqa: E402
from pactiva_core.qr_engine import _cleanup_nonce_cache  # noqa: E402


@pytest.fixture
def temiz_cache():
    """Test oncesi global durumu sifirla, sonrasini geri yukle."""
    eski_set = set(q._USED_NONCE_CACHE)
    eski_ts = q._LAST_CACHE_CLEANUP
    q._USED_NONCE_CACHE.clear()
    q._LAST_CACHE_CLEANUP = time.time()
    yield q
    q._USED_NONCE_CACHE.clear()
    q._USED_NONCE_CACHE.update(eski_set)
    q._LAST_CACHE_CLEANUP = eski_ts


# == bos cache ==========================================================================================

def test_bos_cache_temizler(temiz_cache):
    """ORTAM: bos cache ile calisir (hata YOK)."""
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


def test_bos_cache_yine_bos(temiz_cache):
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


# == zamanlama dali =====================================================================================

def test_5dk_sonra_temizler(temiz_cache):
    """ORTAM: time.time() - last > 300 -> clear()."""
    temiz_cache._USED_NONCE_CACHE.add("n1")
    temiz_cache._LAST_CACHE_CLEANUP = 0.0  # cok eski
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


def test_5dk_icinde_no_op(temiz_cache):
    """ORTAM-OGRENDI: 5 dk ICINDE -> temizlik YAPILMAZ (no-op)."""
    temiz_cache._USED_NONCE_CACHE.add("n1")
    _cleanup_nonce_cache()
    assert "n1" in temiz_cache._USED_NONCE_CACHE


def test_yakin_zaman_no_op(temiz_cache):
    temiz_cache._USED_NONCE_CACHE.add("n1")
    temiz_cache._LAST_CACHE_CLEANUP = time.time() - 299
    _cleanup_nonce_cache()
    assert "n1" in temiz_cache._USED_NONCE_CACHE


def test_sinir_300_no_op(temiz_cache, monkeypatch):
    """ORTAM-OGRENDI: > 300 STRICT — fark TAM 300 olunca NO-OP (300 > 300
    False). Dondurulmus saat ile epsilon-hatasi olmadan dogrulandi."""
    now = time.time()
    monkeypatch.setattr(q.time, "time", lambda: now)
    temiz_cache._USED_NONCE_CACHE.add("n1")
    temiz_cache._LAST_CACHE_CLEANUP = now - 300
    _cleanup_nonce_cache()
    assert "n1" in temiz_cache._USED_NONCE_CACHE


def test_sinir_301_temizler(temiz_cache, monkeypatch):
    """ORTAM: 301 > 300 -> temizler."""
    now = time.time()
    monkeypatch.setattr(q.time, "time", lambda: now)
    temiz_cache._USED_NONCE_CACHE.add("n1")
    temiz_cache._LAST_CACHE_CLEANUP = now - 301
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


def test_uzak_gecmis_temizler(temiz_cache):
    temiz_cache._USED_NONCE_CACHE.add("n1")
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


def test_gelecek_zaman_no_op(temiz_cache):
    """ORTAM: gelecek ts -> negatif fark -> NO-OP ( > 300 False)."""
    temiz_cache._USED_NONCE_CACHE.add("n1")
    temiz_cache._LAST_CACHE_CLEANUP = time.time() + 1000
    _cleanup_nonce_cache()
    assert "n1" in temiz_cache._USED_NONCE_CACHE


# == timestamp guncelleme ==============================================================================

def test_ts_guncellenir(temiz_cache):
    """ORTAM-OGRENDI: temizlik yapilinca _LAST_CACHE_CLEANUP = time.time()."""
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert temiz_cache._LAST_CACHE_CLEANUP > 0


def test_ts_guncellenir_yakin(temiz_cache, monkeypatch):
    now = time.time()
    monkeypatch.setattr(q.time, "time", lambda: now)
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert temiz_cache._LAST_CACHE_CLEANUP == now


def test_ts_no_op_da_degismez(temiz_cache):
    """ORTAM: temizlik yapilmazsa ts GUNCELLENMEZ."""
    ts = temiz_cache._LAST_CACHE_CLEANUP
    _cleanup_nonce_cache()  # recent -> no-op
    assert temiz_cache._LAST_CACHE_CLEANUP == ts


# == icerik =============================================================================================

def test_cok_nonce_temizler(temiz_cache):
    """ORTAM: TUM nonce'ler clear() ile bosaltilir."""
    for i in range(100):
        temiz_cache._USED_NONCE_CACHE.add(f"n{i}")
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


def test_unicode_nonce_temizler(temiz_cache):
    temiz_cache._USED_NONCE_CACHE.add("nonce-ö-🎉")
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


def test_tek_nonce_temizler(temiz_cache):
    temiz_cache._USED_NONCE_CACHE.add("tek")
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert "tek" not in temiz_cache._USED_NONCE_CACHE


def test_ekleme_sonrasi_no_op_korur(temiz_cache):
    """ORTAM: temizlik sonrasi eklenen nonce BIR sonraki temizlige kadar kalir."""
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()  # simdi temizlendi, ts=guncel
    temiz_cache._USED_NONCE_CACHE.add("yeni")
    _cleanup_nonce_cache()  # recent -> no-op
    assert "yeni" in temiz_cache._USED_NONCE_CACHE


def test_iki_temizlik_arasi(temiz_cache):
    """ORTAM: temizlik -> ekleme -> 5dk bekle -> temizlik."""
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    temiz_cache._USED_NONCE_CACHE.update(["a", "b", "c"])
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


def test_set_tipi(temiz_cache):
    """ORTAM: cache bir Set[str]."""
    assert isinstance(temiz_cache._USED_NONCE_CACHE, set)


def test_ts_float(temiz_cache):
    assert isinstance(temiz_cache._LAST_CACHE_CLEANUP, float)


# == kararlik / karakterizasyon ==========================================================================

def test_stabil_idempotent(temiz_cache):
    """ORTAM: ayni ts ile 2 kez temizlik -> 2. kez zaten bos."""
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 0


def test_temizlik_sonrasi_yeni_pencere(temiz_cache):
    """ORTAM-OGRENDI: temizlik sonrasi ts YENI pencere baslatir —
    5 dk boyunca tum yeni nonce'ler KORUNUR (sliding-window)."""
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    for i in range(50):
        temiz_cache._USED_NONCE_CACHE.add(f"p{i}")
    _cleanup_nonce_cache()
    assert len(temiz_cache._USED_NONCE_CACHE) == 50


def test_replay_koruma_amaci(temiz_cache):
    """ORTAM-OGRENDI (AKADEMIK): _USED_NONCE_CACHE replay-saldiri korumasidir —
    eski nonce'ler 5 dk sonra bosaltilir (memory-bomba onlenir), ama pencere
    icinde TEKRAR KULLANIM engellenir (cache hala dolu). Bu DENGE:
    replay-koruma (5 dk) vs memory (surekli buyume YOK)."""
    temiz_cache._USED_NONCE_CACHE.add("replay-token")
    _cleanup_nonce_cache()
    assert "replay-token" in temiz_cache._USED_NONCE_CACHE  # pencere icinde
    temiz_cache._LAST_CACHE_CLEANUP = 0.0
    _cleanup_nonce_cache()
    assert "replay-token" not in temiz_cache._USED_NONCE_CACHE  # 5 dk sonrasi
