"""
Tests for previously-untested critical Pactiva functions (AST-discovered):
  - compute_block_hash      (audit_ledger.py — Proof-of-Audit blok özeti)
  - PactaEscrowBridge.reconcile (pacta_escrow.py — hak-ediş ↔ escrow uzlaşı)
  - HakEdisRecord.net_payout_amount / expected_usdc (pacta_escrow.py)

Only NEW assertions are added; no existing file is modified.
Pure in-memory logic — no database, network, or escrow node is contacted.
"""

import hashlib

import pytest
from decimal import Decimal

# pactiva_core.pacta_escrow importu pacta'yı sys.path'e ekler (mevcut testlerdeki gibi);
# EscrowJob/EscrowStatus bu sayede çözülür.
# G48-2026-10-22: CI'da kardes-Pacta-checkout-YOKSA-bu-dosyanin-tamami-skip
# ( module-level-pacta-importu-collection-patliyordu).
pytest.importorskip("pacta")
import pactiva_core.pacta_escrow  # noqa: F401

from pactiva_core.audit_ledger import compute_block_hash
from pactiva_core.pacta_escrow import HakEdisRecord, PactaEscrowBridge
from pacta.models import EscrowJob, EscrowStatus


# --------------------------------------------------------- compute_block_hash


def test_compute_block_hash_is_deterministic_sha256():
    h = compute_block_hash(1, "2026-01-01T00:00:00Z", "ESCROW_LOCK", "abc", "def")
    raw = "1:2026-01-01T00:00:00Z:ESCROW_LOCK:abc:def"
    assert h == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_compute_block_hash_has_64_lowercase_hex_chars():
    h = compute_block_hash(7, "t", "ACTION", "p", "prev")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


@pytest.mark.parametrize("field", ["block_index", "created_at", "action_type",
                                   "payload_hash", "prev_block_hash"])
def test_compute_block_hash_is_sensitive_to_every_field(field):
    base = dict(block_index=1, created_at="t", action_type="A",
                payload_hash="p", prev_block_hash="x")
    original = compute_block_hash(**base)
    mutated = dict(base)
    mutated[field] = {"block_index": 2, "created_at": "t2", "action_type": "B",
                      "payload_hash": "p2", "prev_block_hash": "x2"}[field]
    assert compute_block_hash(**mutated) != original


def test_compute_block_hash_links_blocks_into_a_chain():
    # Zincir: her bloğun özeti bir sonrakinin prev değeri olmalı — tek değişiklik
    # geriye dönük olarak tüm özetleri geçersiz kılar.
    b1 = compute_block_hash(1, "t1", "A", "p1", "0" * 64)
    b2 = compute_block_hash(2, "t2", "A", "p2", b1)
    assert b1 != b2
    # Aynı içerikle yeniden hesapla — bayt-bayt aynı olmalı.
    assert compute_block_hash(2, "t2", "A", "p2", b1) == b2


# ---------------------------------------------------------------- reconcile


def _record(**overrides) -> HakEdisRecord:
    kwargs = dict(
        job_id="j1",
        job_title="Saha İstihdamı",
        worker_id="w1",
        employer_id="e1",
        escrow_id="es1",
        gross_locked=Decimal("1000"),
        platform_fee=Decimal("20"),
        withholding_tax=Decimal("30"),
        employer_address="0xAAAA",
        worker_address="0xBBBB",
        audit_block_hash="a" * 64,
    )
    kwargs.update(overrides)
    return HakEdisRecord(**kwargs)


def _job(**overrides) -> EscrowJob:
    kwargs = dict(
        job_id="j1",
        buyer_address="0xAAAA",
        seller_address="0xBBBB",
        amount_usdc=Decimal("100"),
        status=EscrowStatus.SETTLED,
        settlement_tx="0xmesh-tx",
    )
    kwargs.update(overrides)
    return EscrowJob(**kwargs)


def test_reconcile_green_path_all_checks_pass():
    out = PactaEscrowBridge.reconcile(_record(), _job(), Decimal("0.1"))
    assert out["ok"] is True
    assert out["reason"] == "reconciled"
    assert all(out["checks"].values())
    assert out["checks"] == {
        "r1_settled": True,
        "r2_amount": True,
        "r3_parties": True,
        "r4_disbursed_bound": True,
    }
    # 1000 TRY × 0.1 = 100 USDC — quantize 6 ondalık.
    assert out["expected_usdc"] == "100.000000"


def test_reconcile_amount_mismatch_fail_closed():
    out = PactaEscrowBridge.reconcile(_record(), _job(amount_usdc=Decimal("99")),
                                      Decimal("0.1"))
    assert out["ok"] is False
    assert out["reason"] == "pactiva_escrow_mismatch: r2_amount"
    assert out["checks"]["r2_amount"] is False


def test_reconcile_party_mismatch_reports_r3():
    out = PactaEscrowBridge.reconcile(
        _record(), _job(buyer_address="0xZZZZ"), Decimal("0.1"))
    assert out["ok"] is False
    assert "r3_parties" in out["reason"]


def test_reconcile_not_settled_reports_r1():
    out = PactaEscrowBridge.reconcile(
        _record(), _job(status=EscrowStatus.ESCROW_LOCKED, settlement_tx=None),
        Decimal("0.1"))
    assert out["ok"] is False
    assert "r1_settled" in out["reason"]
    assert out["checks"]["r1_settled"] is False


def test_reconcile_locked_earning_is_not_disbursed():
    out = PactaEscrowBridge.reconcile(_record(escrow_status="locked"), _job(),
                                      Decimal("0.1"))
    assert out["ok"] is False
    assert "r4_disbursed_bound" in out["reason"]


def test_reconcile_missing_fx_rate_is_indeterminate_amount():
    # TRY kaydı + kur yok → expected None → r2 fail-closed (değer sabitlenemez).
    out = PactaEscrowBridge.reconcile(_record(), _job(), None)
    assert out["ok"] is False
    assert out["expected_usdc"] is None
    assert out["checks"]["r2_amount"] is False


def test_reconcile_parties_compared_case_insensitively():
    out = PactaEscrowBridge.reconcile(
        _record(employer_address="0xaaaa", worker_address="0xbbbb"),
        _job(), Decimal("0.1"))
    assert out["ok"] is True
    assert out["checks"]["r3_parties"] is True


def test_reconcile_amount_within_tolerance_passes():
    # Tolerance = 1e-6 USDC: bir mikron altında sapma uzlaşıyı bozmamalı.
    out = PactaEscrowBridge.reconcile(
        _record(), _job(amount_usdc=Decimal("100.0000005")), Decimal("0.1"))
    assert out["ok"] is True


# ------------------------------------------- net_payout_amount / expected_usdc


def test_net_payout_subtracts_fee_and_tax():
    r = _record()
    net = r.net_payout_amount()
    assert isinstance(net, Decimal)
    assert net == Decimal("950.000000")   # 1000 − 20 − 30


def test_net_payout_quantized_to_six_decimals_half_up():
    r = _record(gross_locked=Decimal("100"), platform_fee=Decimal("0.005"),
                withholding_tax=Decimal("0.005"))
    assert r.net_payout_amount() == Decimal("99.990000")


def test_net_payout_never_implicit_negative_clause():
    # Brüt == pay + stopaj → net tam 0 (negatif olamaz).
    r = _record(gross_locked=Decimal("50"), platform_fee=Decimal("20"),
                withholding_tax=Decimal("30"))
    assert r.net_payout_amount() == Decimal("0.000000")


def test_expected_usdc_applies_fx_rate():
    r = _record()
    assert r.expected_usdc(Decimal("0.1")) == Decimal("100.000000")
    assert r.expected_usdc(Decimal("0.25")) == Decimal("250.000000")


def test_expected_usdc_is_none_without_fx_for_try():
    assert _record().expected_usdc(None) is None


def test_expected_usdc_usdc_uses_unit_rate_without_fx():
    r = _record(currency="USDC")
    assert r.expected_usdc(None) == Decimal("1000.000000")


def test_earning_hash_is_reproducible_from_canonical():
    r = _record()
    # earning_hash, sha256(jcs(canonical)) olmalı — bağımsız yeniden-üretilebilir
    # (jcs RFC 8785 canonicalization; modülün kullandığı aynı fonksiyon).
    from pacta.integrations.tamga_jcs import jcs

    recomputed = hashlib.sha256(jcs(r.canonical())).hexdigest()
    assert r.earning_hash == recomputed
    assert len(r.earning_hash) == 64
