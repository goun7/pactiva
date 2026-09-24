"""
Pactiva CLI Testleri (tests/test_cli.py)
"""

import subprocess
import sys
import pytest


def test_cli_status():
    res = subprocess.run([sys.executable, "-m", "pactiva_core.cli", "status"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "PACTIVA ENTERPRISE INFRASTRUCTURE STATUS" in res.stdout


def test_cli_lock_budget():
    cmd = [
        sys.executable,
        "-m",
        "pactiva_core.cli",
        "lock-budget",
        "--title",
        "Test CLI Mesai",
        "--rate",
        "300",
        "--hours",
        "8",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Bütçe Başarıyla Kilitlendi" in res.stdout
    assert "2880.00 TL" in res.stdout  # 300 * 8 * 1.20 = 2880.00


def test_cli_qr_generate():
    res = subprocess.run([sys.executable, "-m", "pactiva_core.cli", "generate-qr"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "15-Saniyelik Dönen QR Tokeni" in res.stdout
    assert "PACTIVA:" in res.stdout


def test_cli_dispatch():
    res = subprocess.run([sys.executable, "-m", "pactiva_core.cli", "dispatch"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Acil Yedekleme Sonucu" in res.stdout
    assert "DISPATCH_OFFERED" in res.stdout


def test_cli_contract():
    cmd = [
        sys.executable,
        "-m",
        "pactiva_core.cli",
        "contract",
        "--title",
        "Test Sözleşme İlanı",
        "--rate",
        "400",
        "--hours",
        "10",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Yasal Üçlü Sözleşme Tanzim Edildi" in res.stdout
    assert "SGK Müteselsil İzolasyonu ONAYLI" in res.stdout


def test_cli_audit_verify():
    res = subprocess.run([sys.executable, "-m", "pactiva_core.cli", "audit-verify"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "PACTIVA KRİPTOGRAFİK DENETİM ZİNCİRİ" in res.stdout
    assert "KUSURSUZ" in res.stdout


def test_cli_erp_export():
    res = subprocess.run([sys.executable, "-m", "pactiva_core.cli", "erp-export", "--format", "json"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "MAHSUP_FISI" in res.stdout or "[]" in res.stdout


def test_cli_in_process_execution(monkeypatch, capsys):
    from pactiva_core.cli import main
    # 1. status
    monkeypatch.setattr(sys, "argv", ["pactiva", "status"])
    main()
    out = capsys.readouterr().out
    assert "PACTIVA ENTERPRISE INFRASTRUCTURE STATUS" in out

    # 2. audit-verify
    monkeypatch.setattr(sys, "argv", ["pactiva", "audit-verify"])
    main()
    out_audit = capsys.readouterr().out
    assert "PACTIVA KRİPTOGRAFİK DENETİM ZİNCİRİ" in out_audit

    # 3. erp-export
    monkeypatch.setattr(sys, "argv", ["pactiva", "erp-export", "--format", "logo_xml"])
    main()
    out_erp = capsys.readouterr().out
    assert "<TRANSACTIONS>" in out_erp or "GL_VOUCHERS" in out_erp
