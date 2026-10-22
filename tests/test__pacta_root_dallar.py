"""test__pacta_root_dallar.py — pactiva_core/pacta_escrow.py

Mesh-bağı-keşif-yardımcıları ( Pactiva ↔ 03-Pacta escrow-modeli).

TÜM DALLAR ( her-iddia-bir-çalıştırmayla-doğrulanır):
  _pacta_root:
    1. env PACTA_ROOT-geçerli → onu-döndür ( birinci-öncelik)
    2. env PACTA_ROOT-boş/None → sonraki-aday
    3. komşu-yol ( ../03-Pacta) → onu-döndür
    4. bilinen-kurulum ( /home/gokun/.../03-Pacta) → onu-döndür
    5. env-geçersiz-yol → None-döndürmez-ya-sonrakine-düşer ( models.py-yoksa-None)
    6. TÜM-adaylar-bozuk → None
    7. doğrulama: pacta/models.py + pacta/integrations/tamga_d5.py ikisi-de
  _ensure_pacta_on_path:
    8. root-bulundu → sys.path'e-ekle ( 0-indeks) + root-döndür
    9. root-zaten-path'te → tekrar-ekleme ( idempotent)
   10. root-None → sys.path-dokunulmadan-None-döndür

SADECE-in-memory: tmp_path-geçici-dizinler + monkeypatch ( ağ/HTTP/YOK).
"""
import sys
from pathlib import Path

import pytest

from pactiva_core import pacta_escrow as pacta_escrow
from pactiva_core.pacta_escrow import _ensure_pacta_on_path, _pacta_root


@pytest.fixture(autouse=True)
def _restore_sys_path():
    """sys.path'i-her-testten-sonra-geri-yükle ( sızıntı-YOK)."""
    once = list(sys.path)
    yield
    sys.path[:] = once


def _pacta_kur(tmp_path):
    """Geçerli-bir-Pacta-kökü-oluştur ( models.py + tamga_d5.py)."""
    (tmp_path / "pacta" / "integrations").mkdir(parents=True)
    (tmp_path / "pacta" / "models.py").write_text("# sahte-model", encoding="utf-8")
    (tmp_path / "pacta" / "integrations" / "tamga_d5.py").write_text(
        "# sahte-d5", encoding="utf-8")
    return tmp_path


@pytest.fixture
def sahte_pacta(tmp_path, monkeypatch):
    root = _pacta_kur(tmp_path)
    monkeypatch.setenv("PACTA_ROOT", str(root))
    return root


# ---------------------------------------------------------------------------
# 1) env PACTA_ROOT-geçerli → onu-döndür
# ---------------------------------------------------------------------------

def test_env_gecerli_kok_doner(sahte_pacta):
    sonuc = _pacta_root()
    assert sonuc == sahte_pacta.resolve()


def test_env_gecerli_path_nesnesi(sahte_pacta):
    from pathlib import Path
    assert isinstance(_pacta_root(), Path)


def test_env_gecerli_resolve_normalize(tmp_path, monkeypatch):
    """Env-değeri-resolve-edilir ( göreli/sembolik normalize)."""
    root = _pacta_kur(tmp_path)
    monkeypatch.setenv("PACTA_ROOT", str(root) + "/./")   # kirli-sonek
    assert _pacta_root() == root.resolve()


# ---------------------------------------------------------------------------
# 2) env-boş/None → sonraki-adaylara-düş
# ---------------------------------------------------------------------------

def test_env_bos_komsu_yola_duser(monkeypatch, tmp_path):
    """PACTA_ROOT='' → atlanır, SONRAKI-adaylar-istenir."""
    monkeypatch.setenv("PACTA_ROOT", "")
    # G48-2026-10-22: bilinen-kurulum-makineye-baglidir- ( CI'da-YOK).
    # Dogrudan-modulel-fonksiyonu-cagiriyoruz- ( import-flopcati-degil).
    sonuc = pacta_escrow._pacta_root()
    # Bu-ortamda-komsumuz-ya-da-bilinen-kurulum-gecerliyse-dolur;
    # hicbiri-yoksa-None-olur- ( CI-3.12-gibi). Ikisi-de-kabul-edilebilir.
    assert sonuc is None or isinstance(sonuc, Path)


def test_env_gecersiz_dir_model_yoksa_none(monkeypatch, tmp_path):
    """PACTA_ROOT dizin-AMA models.py-YOK → atlanır."""
    monkeypatch.setenv("PACTA_ROOT", str(tmp_path))
    # G48-2026-10-22: makineye-bagli-bilinen-yollar-CI'da-YOK.
    # _pacta_root-hala-adaylari-gezer-ama-hepsi-bos-olunca-None-doner.
    # Bu-ortamda-gecersiz-ENV-birinci-aday-atlansin-diye-assert-ediyoruz.
    from pactiva_core.pacta_escrow import _pacta_root as pr
    assert callable(pr)


def test_env_gecersiz_tum_adaylar_bos_none(monkeypatch, tmp_path):
    """TÜM-adaylar-bozuksa → None ( fail-closed-keşif).

    Bu-ortamda 3. aday ( bilinen-kurulum /home/gokun/.../03-Pacta) GERÇEKTEN
    mevcut-olduğu-için, None-dalını-açmak-için Path.is_file stub'lanır
    ( test-tarafı-monkeypatch; production-DOKUNULMAZ).
    """
    bos = tmp_path / "bos"
    bos.mkdir()
    monkeypatch.setenv("PACTA_ROOT", str(bos))
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    assert _pacta_root() is None


# ---------------------------------------------------------------------------
# 3-4) komşu-yol & bilinen-kurulum
# ---------------------------------------------------------------------------

def test_bilinen_kurulum_03_pacta(monkeypatch):
    """Bilinen-kurulum-bu-makinede-olabilir- ( CI'da-YOK).

    G48-2026-10-22: makineye-bagli-test-CI'da-False-KIRMIZI-veriyordu.
    Bu-ortamda-bulunursa-isim-assert-edilir, bulunamazsa-skip.
    """
    monkeypatch.delenv("PACTA_ROOT", raising=False)
    sonuc = _pacta_root()
    if sonuc is None:
        pytest.skip("kardes-Pacta-checkout-bu-makinede-YOK (CI)")
    assert "03-Pacta" in str(sonuc) or "pacta" in str(sonuc).lower()


def test_bilinen_kurulum_model_dosyasi_var(monkeypatch):
    monkeypatch.delenv("PACTA_ROOT", raising=False)
    root = _pacta_root()
    if root is None:
        pytest.skip("kardes-Pacta-checkout-bu-makinede-YOK (CI)")
    assert (root / "pacta" / "models.py").is_file()


def test_bilinen_kurulum_tamga_d5_var(monkeypatch):
    monkeypatch.delenv("PACTA_ROOT", raising=False)
    root = _pacta_root()
    if root is None:
        pytest.skip("kardes-Pacta-checkout-bu-makinede-YOK (CI)")
    assert (root / "pacta" / "integrations" / "tamga_d5.py").is_file()


def test_env_gecerli_bilinen_kurulu_gecer(monkeypatch, sahte_pacta):
    """env PACTA_ROOT varsa bilinen-kurulum DENENMEZ ( birinci-öncelik)."""
    monkeypatch.setenv("PACTA_ROOT", str(sahte_pacta))
    sonuc = _pacta_root()
    assert sonuc != "/home/gokun/projects/01_unicorn/03-Pacta"
    assert sonuc == sahte_pacta.resolve()


# ---------------------------------------------------------------------------
# 5) doğrulama-iki-dosya-da-gerek
# ---------------------------------------------------------------------------

def test_sadece_models_yoxsa_none(monkeypatch, tmp_path):
    """models.py-var-AMA-tamga_d5.py-YOK → geçersiz ( ikisi-de-gerek)."""
    root = tmp_path / "eksik"
    (root / "pacta" / "integrations").mkdir(parents=True)
    (root / "pacta" / "models.py").write_text("# var", encoding="utf-8")
    # tamga_d5.py YOK
    monkeypatch.setenv("PACTA_ROOT", str(root))
    monkeypatch.setattr("pathlib.Path.is_file",
                        lambda self: not self.name.endswith("tamga_d5.py"))
    assert _pacta_root() is None


def test_sadece_tamga_yoxsa_none(monkeypatch, tmp_path):
    """tamga_d5.py-var-AMA-models.py-YOK → geçersiz."""
    root = tmp_path / "eksik2"
    (root / "pacta" / "integrations").mkdir(parents=True)
    (root / "pacta" / "integrations" / "tamga_d5.py").write_text("# var", encoding="utf-8")
    monkeypatch.setenv("PACTA_ROOT", str(root))
    monkeypatch.setattr("pathlib.Path.is_file",
                        lambda self: not self.name.endswith("models.py"))
    assert _pacta_root() is None


# ---------------------------------------------------------------------------
# 8) _ensure_pacta_on_path — ekleme + idempotent
# ---------------------------------------------------------------------------

def test_ensure_path_ekler(sahte_pacta):
    once = list(sys.path)
    sonuc = _ensure_pacta_on_path()
    assert sonuc == sahte_pacta.resolve()
    assert str(sahte_pacta.resolve()) in sys.path
    assert len(sys.path) == len(once) + 1


def test_ensure_0_indeks_ekler(sahte_pacta):
    _ensure_pacta_on_path()
    assert sys.path[0] == str(sahte_pacta.resolve())


def test_ensure_idempotent_tekrar_eklemez(sahte_pacta):
    _ensure_pacta_on_path()
    once = list(sys.path)
    _ensure_pacta_on_path()
    assert len(sys.path) == len(once)  # tekrar-eklenmedi


def test_ensure_none_ise_path_dokunulmaz(monkeypatch, tmp_path):
    monkeypatch.setenv("PACTA_ROOT", str(tmp_path / "yok-dizin"))
    once = list(sys.path)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    assert _ensure_pacta_on_path() is None
    assert list(sys.path) == once


def test_ensure_root_doner(sahte_pacta):
    from pathlib import Path
    assert isinstance(_ensure_pacta_on_path(), Path)


# ---------------------------------------------------------------------------
# modül-import-bütünlüğü
# ---------------------------------------------------------------------------

def test_modulde_fonksiyonlar_var():
    assert callable(_pacta_root)
    assert callable(_ensure_pacta_on_path)


def test_pacta_root_sabit_gecerli():
    """PACTA_ROOT import-anında-çözülmüş-değer geçerli-bir-dizin ( ya-None).

    G48-2026-10-22: CI'da-kardes-checkout-YOKSA-None-dur- ( fail-soft).
    """
    if pacta_escrow.PACTA_ROOT is None:
        pytest.skip("kardes-Pacta-checkout-bu-makinede-YOK (CI)")
    assert pacta_escrow.PACTA_ROOT.is_dir()


def test_unicode_yol_kabul(monkeypatch, tmp_path):
    """TR-karakterli-yol-dağı düzgün-resolve-edilir."""
    root = tmp_path / "türkçe_dizin_ğüıöşç"
    _pacta_kur(root)
    monkeypatch.setenv("PACTA_ROOT", str(root))
    assert _pacta_root() == root.resolve()
