"""test__cleanup_nonce_cache_dallar.py — pactiva_core/qr_engine.py

Replay-koruması nonce-önbelleği için 5-dakikalık-temizlik-dal-ları.

TÜM DALLAR ( her-iddia-bir-çalıştırmayla-doğrulanır):
  1. süre-dolmadı ( now-last <= 300) → HİÇBİR-ŞEY-yapma ( önbellek-korunur)
  2. süre-doldu ( > 300) → önbellek-TAMAMEN-boşaltılır + last=now
  3. boundary: tam-300 → temizlik-YOK ( '>'-değil)
  4. boş-önbellek + süre-doldu → hâlâ-boş + zaman damgası-güncellenir
  5. None-döner ( yan-etki-only-fonksiyon)
  6. modül-global'leri-doğru-anahtarlarla-günceller

SADECE-in-memory: time.time monkeypatch ( gerçek-zaman-bekleme-YOK).
"""
import time

import pytest

from pactiva_core import qr_engine
from pactiva_core.qr_engine import _cleanup_nonce_cache, _USED_NONCE_CACHE


@pytest.fixture(autouse=True)
def _isolate_nonce_cache():
    """Global önbelleği her-testten-önce/sonra sıfırla ( sızıntı-YOK)."""
    _USED_NONCE_CACHE.clear()
    qr_engine._LAST_CACHE_CLEANUP = 0.0
    yield
    _USED_NONCE_CACHE.clear()
    qr_engine._LAST_CACHE_CLEANUP = 0.0


@pytest.fixture
def fake_clock(monkeypatch):
    state = {"t": 1000.0}
    monkeypatch.setattr(time, "time", lambda: state["t"])
    return state


# ---------------------------------------------------------------------------
# 1) süre-dolmadı → önbellek-korunur
# ---------------------------------------------------------------------------

def test_sure_dolmadi_onbellegi_koru(fake_clock):
    _USED_NONCE_CACHE.update({"a", "b", "c"})
    qr_engine._LAST_CACHE_CLEANUP = 900.0          # 100-sn-geçmiş < 300
    _cleanup_nonce_cache()
    assert _USED_NONCE_CACHE == {"a", "b", "c"}


@pytest.mark.parametrize("gecikme", [0, 1, 100, 299, 299.999, 300])
def test_sure_dolmadi_sinir_300_dahil(fake_clock, gecikme):
    """300-sn-dahil temizlik-YOK ( '>'-boundary — tam-300 temizlemez)."""
    _USED_NONCE_CACHE.add("nonce-1")
    qr_engine._LAST_CACHE_CLEANUP = 1000.0
    fake_clock["t"] = 1000.0 + gecikme
    _cleanup_nonce_cache()
    assert _USED_NONCE_CACHE == {"nonce-1"}


def test_sure_dolmadi_zaman_damgasi_degismez(fake_clock):
    qr_engine._LAST_CACHE_CLEANUP = 950.0
    _cleanup_nonce_cache()
    assert qr_engine._LAST_CACHE_CLEANUP == 950.0


# ---------------------------------------------------------------------------
# 2) süre-doldu → temizle + zaman damgasını-güncelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("gecikme", [300.001, 301, 600, 3600])
def test_sure_doldu_onbellegi_bosalt(fake_clock, gecikme):
    _USED_NONCE_CACHE.update({"a", "b", "c", "d"})
    qr_engine._LAST_CACHE_CLEANUP = 1000.0
    fake_clock["t"] = 1000.0 + gecikme
    _cleanup_nonce_cache()
    assert _USED_NONCE_CACHE == set()


def test_sure_doldu_zaman_damgasini_guncelle(fake_clock):
    qr_engine._LAST_CACHE_CLEANUP = 1.0
    fake_clock["t"] = 1_000.0
    _cleanup_nonce_cache()
    assert qr_engine._LAST_CACHE_CLEANUP == 1_000.0


def test_sure_doldu_bos_onbellek_bos_kalir(fake_clock):
    """Zaten-boş-önbellek + süre-dolu → boş + damar-güncellenir."""
    qr_engine._LAST_CACHE_CLEANUP = 0.0
    fake_clock["t"] = 500.0
    _cleanup_nonce_cache()
    assert _USED_NONCE_CACHE == set()
    assert qr_engine._LAST_CACHE_CLEANUP == 500.0


def test_sure_doldu_tek_netcice_temizlenir(fake_clock):
    _USED_NONCE_CACHE.add("tek-nonce")
    qr_engine._LAST_CACHE_CLEANUP = 0.0
    fake_clock["t"] = 301.0
    _cleanup_nonce_cache()
    assert len(_USED_NONCE_CACHE) == 0


# ---------------------------------------------------------------------------
# 3) yan-etki-only → None-döner
# ---------------------------------------------------------------------------

def test_none_doner_sure_dolmadi(fake_clock):
    qr_engine._LAST_CACHE_CLEANUP = fake_clock["t"]
    assert _cleanup_nonce_cache() is None


def test_none_doner_sure_doldu(fake_clock):
    qr_engine._LAST_CACHE_CLEANUP = 0.0
    fake_clock["t"] = 1000.0
    assert _cleanup_nonce_cache() is None


# ---------------------------------------------------------------------------
# 4) modül-global'leri-doğru-anahtarlarla-günceller
# ---------------------------------------------------------------------------

def test_global_set_nesnesini_degistirir(fake_clock):
    """Aynı-set-nesnesi-mutasyona-uğrar ( yenisi-oluşturulmaz)."""
    once = id(_USED_NONCE_CACHE)
    qr_engine._LAST_CACHE_CLEANUP = 0.0
    fake_clock["t"] = 1000.0
    _cleanup_nonce_cache()
    assert id(_USED_NONCE_CACHE) == once


def test_sayac_boyutu_sifira_iner(fake_clock):
    for i in range(50):
        _USED_NONCE_CACHE.add(f"n{i}")
    qr_engine._LAST_CACHE_CLEANUP = 0.0
    fake_clock["t"] = 1_000.0
    _cleanup_nonce_cache()
    assert len(_USED_NONCE_CACHE) == 0


# ---------------------------------------------------------------------------
# 5) arka-arkaya-çağrılar — damar-bir-kezi-güncellenir
# ---------------------------------------------------------------------------

def test_arka_arkaya_cagri_damari_gunceller(fake_clock):
    qr_engine._LAST_CACHE_CLEANUP = 0.0
    fake_clock["t"] = 1_000.0
    _cleanup_nonce_cache()
    assert qr_engine._LAST_CACHE_CLEANUP == 1_000.0

    # pencere-içinde tekrar → damar-değişmez
    _USED_NONCE_CACHE.add("yeni")
    fake_clock["t"] = 1_200.0
    _cleanup_nonce_cache()
    assert _USED_NONCE_CACHE == {"yeni"}


def test_unicode_nonce_temizlenir(fake_clock):
    """TR/unicode nonce-değerleri de temizlik-dışında-kalmaz."""
    _USED_NONCE_CACHE.update({"kiracı-çiftçi-nonce", "ğüıöşç", "😀-nonce"})
    qr_engine._LAST_CACHE_CLEANUP = 0.0
    fake_clock["t"] = 1_000.0
    _cleanup_nonce_cache()
    assert _USED_NONCE_CACHE == set()


def test_temizlik_sonrasi_replay_tekrar_gecerli(fake_clock):
    """Temizlik-sonrası eski-nonce tekrar-kullanılabilir ( 5-dk-pencere)."""
    _USED_NONCE_CACHE.add("job:shift:win:nonce-abc")
    qr_engine._LAST_CACHE_CLEANUP = 0.0

    fake_clock["t"] = 1_000.0                      # > 300 → temizle
    _cleanup_nonce_cache()
    assert "job:shift:win:nonce-abc" not in _USED_NONCE_CACHE


def test_time_time_kullaniliyor(monkeypatch):
    """time.time kullanıldığını doğrula ( gerçek-zaman-sızıntısı-YOK)."""
    cagri = {"n": 0}

    def _fake():
        cagri["n"] += 1
        return 5.0

    monkeypatch.setattr(time, "time", _fake)
    qr_engine._LAST_CACHE_CLEANUP = 0.0            # 5-0=5 < 300 → temizlik-yok
    _cleanup_nonce_cache()
    assert cagri["n"] == 1
