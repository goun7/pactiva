"""
Pactiva CLI RC-Pin'leri (DALGA-D2) — docs/CLI_RC_MATRISI.md ile uyumlu.

Olcum-yontemi: subprocess, un-piped degil capture_output (gercek-exit-code
captured-stdout/traceback'le birlikte alinir; hiuceboru-yok, rc maskelenmez).

Sozlesme (argparse stdlib):
- rc=0  -> basarili
- rc=2  -> GECELERSIZ-GIRDI / kullanma-hatasi (usage error, traceback YOK)
- rc=1  -> calisma-zamani hatasi (traceback) — gecersiz-girdi icin ASLA olmamali

DALGA-KURALI: gecersiz-girdi rc=1/traceback veriyorsa test KIRMIZI birakilir,
raporlanir, uretime-DOKUNULMAZ (duzeltme D3'ye-rafta).

Matris-ozeti (olculen, PACTIVA_DB_PATH=/tmp'ye-yonelik):
- status/lock-budget/release-escrow/generate-qr/dispatch/contract/audit-verify/erp-export
- rc=2 (dogru): --rate abc, --hours abc, --payout abc, --format xml,
  eksik --title, bilinmeyen-komut, argsiz-calistirma
- rc=1 (BULGU, traceback): lock-budget --rate -5, lock-budget --hours -5,
  release-escrow var-olmayan-job-id
- rc=0 (zayif-dogrulama-notu): lock-budget --title "" (bos-baslik sessiz-kabul)
"""

import os
import subprocess
import sys
import uuid

import pytest

# conftest.py PACTIVA_DB_PATH'i tmp'ye yonlendirir; subprocess env'i miras alir.

CLI = [sys.executable, "-m", "pactiva_core.cli"]


def _run(*args):
    return subprocess.run(CLI + list(args), capture_output=True, text=True)


# ---------------------------------------------------------------------------
# 1) GECERLI-YOLLAR (tum komutlar) — rc=0 pin'leri
# ---------------------------------------------------------------------------


def test_pin_status_valid_rc0():
    res = _run("status")
    assert res.returncode == 0
    assert "PACTIVA ENTERPRISE INFRASTRUCTURE STATUS" in res.stdout


def test_pin_lock_budget_valid_rc0():
    res = _run("lock-budget", "--title", "RC-Pin Test İlanı", "--rate", "300", "--hours", "8")
    assert res.returncode == 0
    assert "Bütçe Başarıyla Kilitlendi" in res.stdout
    assert "2880.00 TL" in res.stdout  # 300*8*1.20


def test_pin_release_escrow_lifecycle_rc0():
    """lock-budget sonra release-escrow → her ikisi de rc=0."""
    lock = _run("lock-budget", "--title", "Release Lifecycle", "--rate", "300", "--hours", "8")
    assert lock.returncode == 0
    job_id = lock.stdout.split("İlan ID")[1].split(":")[1].split()[0].strip()
    rel = _run("release-escrow", "--job-id", job_id, "--payout", "250", "--tax", "25")
    assert rel.returncode == 0
    assert "Hak Ediş Ödendi" in rel.stdout


def test_pin_generate_qr_valid_rc0():
    res = _run("generate-qr")
    assert res.returncode == 0
    assert "15-Saniyelik Dönen QR Tokeni" in res.stdout
    assert "PACTIVA:" in res.stdout


def test_pin_dispatch_valid_rc0():
    res = _run("dispatch")
    assert res.returncode == 0
    assert "Acil Yedekleme Sonucu" in res.stdout
    assert "DISPATCH_OFFERED" in res.stdout


def test_pin_contract_valid_rc0():
    res = _run("contract", "--title", "Pin Sözleşme", "--rate", "400", "--hours", "10")
    assert res.returncode == 0
    assert "Yasal Üçlü Sözleşme Tanzim Edildi" in res.stdout
    assert "SGK Müteselsil İzolasyonu ONAYLI" in res.stdout


def test_pin_audit_verify_valid_rc0():
    res = _run("audit-verify")
    assert res.returncode == 0
    assert "PACTIVA KRİPTOGRAFİK DENETİM ZİNCİRİ" in res.stdout
    assert "KUSURSUZ" in res.stdout


@pytest.mark.parametrize("fmt,needle", [
    ("json", "MAHSUP_FISI"),
    ("logo_xml", "<TRANSACTIONS>"),
    ("sap_csv", "POSTING_DATE;DOCUMENT_TYPE"),  # bos-fatura durumu: sadece CSV basligi
])
def test_pin_erp_export_valid_rc0(fmt, needle):
    res = _run("erp-export", "--format", fmt)
    assert res.returncode == 0
    assert needle in res.stdout or fmt == "json" and "[]" in res.stdout


def test_pin_help_rc0():
    res = _run("--help")
    assert res.returncode == 0
    assert "Pactiva Enterprise CLI" in res.stdout
    for cmd in ("status", "lock-budget", "release-escrow", "generate-qr",
                "dispatch", "contract", "audit-verify", "erp-export"):
        assert cmd in res.stdout


def test_pin_subcommand_help_rc0():
    res = _run("lock-budget", "--help")
    assert res.returncode == 0
    assert "--rate" in res.stdout and "--hours" in res.stdout


# ---------------------------------------------------------------------------
# 2) GECERSIZ-GIRDI → rc=2 (argparse dogru-davranis pin'leri — YEŞIL)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("args,label", [
    (("lock-budget", "--title", "X", "--rate", "abc", "--hours", "8"), "rate-abc"),
    (("lock-budget", "--title", "X", "--rate", "300", "--hours", "abc"), "hours-abc"),
    (("lock-budget", "--rate", "300", "--hours", "8"), "missing-required-title"),
    (("lock-budget", "--title", "X", "--rate", "300", "--hours", "8",
      "--category", "bogus"), "bad-category-choice"),
    (("dispatch", "--rate", "abc"), "dispatch-rate-abc"),
    (("contract", "--hours", "abc"), "contract-hours-abc"),
    (("contract", "--rate", "abc"), "contract-rate-abc"),
    (("release-escrow", "--job-id", "x", "--payout", "abc"), "payout-abc"),
    (("erp-export", "--format", "xml"), "bad-format-choice"),
    (("bogus-command",), "unknown-command"),
    ((), "no-subcommand"),
])
def test_pin_invalid_input_rc2(args, label, subtests=None):
    res = _run(*args)
    assert res.returncode == 2, f"[{label}] rc={res.returncode}, stderr={res.stderr[-400:]}"
    assert "Traceback" not in res.stderr, f"[{label}] argparse yerine traceback!"


# ---------------------------------------------------------------------------
# 3) GECERSIZ-GIRDI → rc=1 TRACEBACK (DALGA-kurali: KIRMIZI birakilir)
#    Beklenen rc=2 (girdi-dogrulama usage-seviyesinde). Olculen: rc=1 + ValueError.
#    Uretime-DOKUNULMAZ — duzeltme (positive-range type-guard) D3'ye-rafta.
# ---------------------------------------------------------------------------


def test_red_pin_lock_budget_negative_rate_must_be_rc2():
    """Matris LB-N1: `lock-budget --rate -5` → beklenen rc=2, olculen rc=1."""
    res = _run("lock-budget", "--title", "Negatif Ücret", "--rate", "-5", "--hours", "8")
    assert res.returncode == 2, (
        f"KIRMIZI: gecersiz-girdi rc=1/traceback veriyor (beklenen rc=2). "
        f"olculen rc={res.returncode}, hata={res.stderr.strip().splitlines()[-1] if res.stderr else ''}"
    )


def test_red_pin_lock_budget_negative_hours_must_be_rc2():
    """Matris LB-N2: `lock-budget --hours -5` → beklenen rc=2, olculen rc=1."""
    res = _run("lock-budget", "--title", "Negatif Süre", "--rate", "300", "--hours", "-5")
    assert res.returncode == 2, (
        f"KIRMIZI: gecersiz-girdi rc=1/traceback veriyor (beklenen rc=2). "
        f"olculen rc={res.returncode}, hata={res.stderr.strip().splitlines()[-1] if res.stderr else ''}"
    )


def test_red_pin_release_escrow_missing_job_must_be_rc2():
    """Matris RE-N1: var-olmayan job-id → beklenen rc=2, olculen rc=1."""
    res = _run("release-escrow", "--job-id", str(uuid.uuid4()), "--payout", "100")
    assert res.returncode == 2, (
        f"KIRMIZI: gecersiz-girdi rc=1/traceback veriyor (beklenen rc=2). "
        f"olculen rc={res.returncode}, hata={res.stderr.strip().splitlines()[-1] if res.stderr else ''}"
    )


# ---------------------------------------------------------------------------
# 4) ZAYIF-DOGRULAMA pin'i (bilinen-davranis, rc=0 — GEÇERSİZ değer KABUL)
# ---------------------------------------------------------------------------


def test_pin_lock_budget_empty_title_silently_accepted_rc0():
    """Matris LB-E1: `--title ""` rc=0 — bos-baslik icerik-dogrulamasiz kabul (not)."""
    res = _run("lock-budget", "--title", "", "--rate", "300", "--hours", "8")
    assert res.returncode == 0
    assert "Bütçe Başarıyla Kilitlendi" in res.stdout


# ---------------------------------------------------------------------------
# 5) MODÜL-IMPORT YAN-ETKISI — pactiva_core/api.py:96 init_db() module-level
#    PACTIVA_DB_PATH tmp'ye-yonelmisken import CWD'ye (repo-root) YAZMAMALI.
# ---------------------------------------------------------------------------


def test_pin_api_import_does_not_write_cwd_db(tmp_path, monkeypatch):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db = tmp_path / "api-import.sqlite3"
    env = {**os.environ, "PACTIVA_DB_PATH": str(db), "PYTHONPATH": repo_root}

    proc = subprocess.run(
        [sys.executable, "-c", "import pactiva_core.api"],
        capture_output=True, text=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, f"api import basarisiz: {proc.stderr[-500:]}"

    # import sonrasi CWD'de (tmp) 'pactiva.db' OLMAMALI
    leaked = [p for p in tmp_path.iterdir() if p.name == "pactiva.db"]
    assert not leaked, f"MODUL-IMPORT CWD'ye pactiva.db yazdi: {leaked}"

    # yonlendirilen tmp DB'si OLUSMALI (init_db gercekten calisti, ama oraya)
    assert db.exists(), "PACTIVA_DB_PATH'e yonlendirilen DB olusmadi — init_db calismadi?"


def test_pin_api_import_without_env_leaks_to_cwd(tmp_path):
    """Env YOKKEN import CWD'ye yazar — bu yan-etki var, conftest env'i KANITLAR."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": repo_root,
        # PACTIVA_DB_PATH bilincli olarak YOK — DEFAULT_DB_PATH ('pactiva.db') devreye girer
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import pactiva_core.api"],
        capture_output=True, text=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, f"api import basarisiz: {proc.stderr[-500:]}"
    assert (tmp_path / "pactiva.db").exists(), "env'siz import DEFAULT_DB_PATH'e yazmali"
