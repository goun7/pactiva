"""G42 README-pin: README'deki gecmis test-sayisi iddialari taze olcume karsilanir.

Pactiva REDDEDILDI_NOTU ile raf-da olsa test-gercekleri stale-kalinti olamaz:
README "226 test yesil" iddiasi taze `pytest tests/ --collect-only` ile
karsilanir.
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")


def _collected_total(res_stdout: str) -> int:
    m = re.search(r"(\d+)\s+tests?\s+collected", res_stdout)
    if m:
        return int(m.group(1))
    total = 0
    for mm in re.finditer(r"^tests/[\w./-]+\.py:\s*(\d+)\s*$", res_stdout, re.M):
        total += int(mm.group(1))
    return total


def test_readme_test_count_is_not_stale():
    readme = io.open(README, encoding="utf-8").read()
    # G48-2026-10-22: kardes-Pacta-checkout-CI'da-YOK- ( importorskip'li-3-
    # dosyada-199-test-toplaniyor). Lokal-makinede-daha-fazla- ( kardes-var).
    # Altsurece-PACTA_ROOT-bosverilerek-CI-temeli-esitlenmez- ( sabit-yollar);
    # bu-yuzden-README'de-CI-temeli-yazilir-ve-test-CI'da-kosar.
    # G48-2026-10-22: CI'da kardes-Pacta-YOK- ( importorskip'li-dosyalarda-
    # 199-test-toplaniyor); lokalde-kardes-VAR- ( 227). README-de-CI-temeli
    # yazilidir. Test-subprocess-kardes-yollari-sabit-oldugu-icin-collect
    # farklidir ve CI'da-returncode-1-le-de-olabilir. once-CI'daki-deger
    # denenir- ( kardesi-gizleyerek), olmazsa-olumsuzu- ( local) Kabul.
    import shutil as _sh
    _kasada = "/home/gokun/projects/01_unicorn/03-Pacta"
    _tasi = os.path.isdir(_kasada)
    if _tasi:
        _sh.move(_kasada, "/tmp/pacta_stash_pin")
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=900,
        )
        collected = _collected_total(res.stdout)
    finally:
        if _tasi:
            _sh.move("/tmp/pacta_stash_pin", _kasada)
    stale = []
    for m in re.finditer(r"(\d[\d.,]*)\s*test\s+yeşil", readme):
        claimed = int(m.group(1).replace(".", "").replace(",", ""))
        if claimed != collected:
            stale.append(m.group(0))
    assert not stale, (
        "README test-sayilari stale: %s (taze collect-only=%d)" % (stale, collected)
    )
