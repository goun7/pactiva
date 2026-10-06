"""
Pactiva ↔ Pacta escrow mesh bağı testleri ( pactiva_core/pacta_escrow.py)

Hak-ediş-kaydı → escrow-settlement-charge → D5-kanıtı köprüsü:
    hak-ediş ( Pactiva emanet-kasası/Proof-of-Audit) ↔ escrow ( Pacta EscrowJob)
    ↔ RFC-010-beş-kontrolü + pactiva-üçü ( 6/7/8)

Bu-testler-GERÇEK-Pactiva-repository'sini ( sqlite) ve-GERÇEK-Pacta-escrow-
modelini-kullanır — sahte-escrow-yok.
"""

import os
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from eth_keys import keys as eth_keys

# Önce-pactiva_core.pacta_escrow-import-edilmeli — o-GERÇEK-Pacta-checkout'unu
# sys.path'e-ekler ( _ensure_pacta_on_path). Sonrasındaki-pacta-importları-bunun-
# sayesinde-çözülür.
from pactiva_core.audit_ledger import record_audit_event
from pactiva_core.database import init_db
from pactiva_core.pacta_escrow import (
    PACTIVA_TAG,
    HakEdisBinding,
    HakEdisRecord,
    PactaEscrowBridge,
    PactaEscrowBridgeError,
)
from pactiva_core.repository import PactivaRepository

from pacta.integrations.tamga_d5 import D5Ledger, SettlementBinder
from pacta.models import EscrowJob, EscrowStatus


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_pacta_escrow.db")
    init_db(db_file)
    return PactivaRepository(db_path=db_file)


def _key() -> eth_keys.PrivateKey:
    return eth_keys.PrivateKey(os.urandom(32))


def _addr(key: eth_keys.PrivateKey) -> str:
    return key.public_key.to_address()


FX_TRY_TO_USDC = Decimal("0.1")          # 1 TRY = 0.1 USDC ( test-kuru)


def _released_earning(temp_repo, *, employer_key, worker_address, worker_id):
    """Gerçek-repo-üzerinde: iş → emanet-kilidi → hak-ediş-serbest-bırakma."""
    emp = temp_repo.create_user(
        national_id_hash=f"emp_{os.urandom(4).hex()}", phone_number_encrypted="enc_p",
        role="employer")
    job = temp_repo.create_job(
        emp["id"], "Drone Operatörü", "film_set",
        Decimal("500.00"), Decimal("8.0"))
    temp_repo.create_escrow_account(
        job_id=job["id"],
        locked_amount=Decimal("4800.00"),
        platform_fee=Decimal("144.00"),
        provider_tx_ref="TX_MESH_01",
    )
    released = temp_repo.release_escrow_payout(
        job_id=job["id"],
        payout_amount=Decimal("4256.00"),
        withholding_tax_amount=Decimal("400.00"),
    )
    audit = record_audit_event(
        "ESCROW_PAYOUT_RELEASED",
        {"job_id": job["id"], "payout_amount": "4256.00",
         "withholding_tax_amount": "400.00"},
        db_path=temp_repo.db_path,
    )
    record = HakEdisRecord.from_escrow_payout(
        released,
        job,
        worker_id=worker_id,
        employer_address=_addr(employer_key),
        worker_address=worker_address,
        audit_block_hash=audit["block_hash"],
    )
    return record, job


def _settled_pacta_job(record, amount_usdc, *, employer_key):
    return EscrowJob(
        job_id=f"pacta-{record.job_id}",
        buyer_address=_addr(employer_key),      # işveren = alıcı/ödeyici
        seller_address=record.worker_address,   # çalışan = satıcı/hak-edilen
        amount_usdc=amount_usdc,
        status=EscrowStatus.SETTLED,
        settlement_tx="0xmesh-settlement-tx",
    )


# -------------------------------------------------------------------- testler


def test_earning_binding_green_path(temp_repo):
    """Tam-boru: hak-ediş → Pacta-escrow-charge → D5-zinciri; 8-kontrol-yeşil."""
    employer_key = _key()
    worker_address = "0x" + "22" * 20
    record, _ = _released_earning(
        temp_repo, employer_key=employer_key, worker_address=worker_address,
        worker_id="worker-mesh-01")

    # 4800.00 TRY × 0.1 = 480.00 USDC
    assert record.gross_locked == Decimal("4800.00")
    assert record.net_payout_amount() == Decimal("4256.000000")
    assert record.expected_usdc(FX_TRY_TO_USDC) == Decimal("480.000000")

    v = PactaEscrowBridge.verify_record(record)
    assert v["verdict"] == "GREEN", v["reason"]

    job = _settled_pacta_job(record, record.expected_usdc(FX_TRY_TO_USDC),
                             employer_key=employer_key)

    with tempfile.TemporaryDirectory() as d:
        ledger = D5Ledger(Path(d) / "d5.jsonl")
        before = ledger.line_count()
        binding = PactaEscrowBridge.bind_earning(
            record, job, ledger, fx_rate=FX_TRY_TO_USDC, payer_signer=employer_key)

        assert isinstance(binding, HakEdisBinding)
        assert binding.reconciliation["ok"] is True
        assert ledger.line_count() == before + 1

        # D5-zinciri-sağlam ( append-sırasında-üçlü-atıldı)
        ok, tip, why = ledger.verify_chain()
        assert ok is True, why
        assert tip == binding.ledger_tip

        # RFC-010-beşi-Pacta'nın-KENDİ-gate'inde-yeşil ( additive-üstküme-kanıtı)
        pacta_own = SettlementBinder.verify_binding(binding.charge, binding.claim)
        assert pacta_own["verdict"] == "GREEN", pacta_own["reason"]

        # pactiva-üçü-eklenince-de-yeşil; 8-kontrolün-tamamı-doğru
        verdict = PactaEscrowBridge.verify_binding(binding.charge, binding.claim)
        assert verdict["verdict"] == "GREEN", verdict["reason"]
        assert verdict["ok"] is True
        assert set(verdict["checks"]) == {
            "1_receipt", "2_claim_sig", "3_settlement_ref", "4_parties",
            "5_evidence_hash", "6_pactiva_proof", "7_earning_recomputes",
            "8_escrow_reconcile"}
        assert all(verdict["checks"].values())

        # charge-gerçek-hak-ediş-fakatlarını-taşıyor
        pa = binding.charge["pactiva"]
        assert pa["escrow_status"] == "disbursed"
        assert pa["net_payout"] == "4256.000000"
        assert pa["expected_usdc"] == "480.000000"
        assert binding.charge["escrow"]["amount_usdc"] == "480.000000"

        # D5 → Pactiva-geri-okuma
        ref = PactaEscrowBridge.pactiva_ref_of(binding.charge)
        assert ref["scheme"] == PACTIVA_TAG
        assert ref["job_id"] == record.job_id
        assert ref["earning_hash"] == record.earning_hash


def test_earning_amount_mismatch_rejected_and_ledger_untouched(temp_repo):
    """Tutar-uyuşmazlığı → RED; hiçbir-şey-zincire-yazılmaz ( fail-closed)."""
    employer_key = _key()
    record, _ = _released_earning(
        temp_repo, employer_key=employer_key, worker_address="0x" + "22" * 20,
        worker_id="worker-mesh-02")

    # Escrow-999-USDC-iddia-ediyor-AMA-hak-ediş-480-USDC-değerinde
    bad_job = _settled_pacta_job(record, Decimal("999.000000"),
                                 employer_key=employer_key)

    with tempfile.TemporaryDirectory() as d:
        ledger = D5Ledger(Path(d) / "d5.jsonl")
        with pytest.raises(PactaEscrowBridgeError, match="reconciliation_failed"):
            PactaEscrowBridge.bind_earning(
                record, bad_job, ledger, fx_rate=FX_TRY_TO_USDC,
                payer_signer=employer_key)
        assert ledger.line_count() == 0, "fail-closed: reddedilen bağ zincire yazılmaz"


def test_not_disbursed_earning_is_red():
    """Serbest-bırakılmamış-kasalar-hak-ediş-değildir — verify_record-RED."""
    employer_key = _key()
    record = HakEdisRecord(
        job_id="job-x", job_title="İskele Ustası", worker_id="w", employer_id="e",
        escrow_id="esc-x", gross_locked=Decimal("3360.00"),
        platform_fee=Decimal("100.80"), withholding_tax=Decimal("0"),
        escrow_status="locked", audit_block_hash="a" * 64,
        employer_address=_addr(employer_key), worker_address="0x" + "22" * 20,
    )
    v = PactaEscrowBridge.verify_record(record)
    assert v["verdict"] == "RED"
    assert v["reason_code"] == 11
    assert v["checks"]["e1_disbursed"] is False

    job = _settled_pacta_job(record, Decimal("336.000000"), employer_key=employer_key)
    with tempfile.TemporaryDirectory() as d:
        ledger = D5Ledger(Path(d) / "d5.jsonl")
        with pytest.raises(PactaEscrowBridgeError, match="record_not_green"):
            PactaEscrowBridge.bind_earning(record, job, ledger,
                                           fx_rate=FX_TRY_TO_USDC)
        assert ledger.line_count() == 0


def test_try_earning_requires_fx_rate_fail_closed():
    """TRY-hak-edişi-için-kur-YOKSA-değer-belirsizdir → RED,-gizlice-geçilmez."""
    employer_key = _key()
    record = HakEdisRecord(
        job_id="job-try", job_title="Kamera Operatörü", worker_id="w",
        employer_id="e", escrow_id="esc-try", gross_locked=Decimal("4800.00"),
        platform_fee=Decimal("144.00"), withholding_tax=Decimal("400.00"),
        currency="TRY", escrow_status="disbursed", audit_block_hash="b" * 64,
        employer_address=_addr(employer_key), worker_address="0x" + "33" * 20,
    )
    assert record.expected_usdc(None) is None, "TRY için kur olmadan değer belirsiz"

    job = _settled_pacta_job(record, Decimal("480.000000"), employer_key=employer_key)
    with tempfile.TemporaryDirectory() as d:
        ledger = D5Ledger(Path(d) / "d5.jsonl")
        with pytest.raises(PactaEscrowBridgeError, match="indeterminate_value"):
            PactaEscrowBridge.bind_earning(record, job, ledger, payer_signer=employer_key)
        assert ledger.line_count() == 0

    # USDC-hak-edişi-için-kur-1'-dir ( denominasyon-aynı)
    usdc_record = HakEdisRecord(
        job_id="job-usdc", job_title="Bağlantı Kurma", worker_id="w", employer_id="e",
        escrow_id="esc-usdc", gross_locked=Decimal("480.000000"),
        platform_fee=Decimal("4.00"), withholding_tax=Decimal("0"),
        currency="USDC", escrow_status="disbursed", audit_block_hash="c" * 64,
        employer_address=_addr(employer_key), worker_address="0x" + "33" * 20,
    )
    assert usdc_record.expected_usdc(None) == Decimal("480.000000")


def test_verify_binding_detects_tampered_charge(temp_repo):
    """Doğrulama-kapısı-tahrif-edilmiş-charge'ı-yakalar ( 6/7/8-RED)."""
    employer_key = _key()
    record, _ = _released_earning(
        temp_repo, employer_key=employer_key, worker_address="0x" + "44" * 20,
        worker_id="worker-mesh-05")
    job = _settled_pacta_job(record, record.expected_usdc(FX_TRY_TO_USDC),
                             employer_key=employer_key)

    with tempfile.TemporaryDirectory() as d:
        ledger = D5Ledger(Path(d) / "d5.jsonl")
        binding = PactaEscrowBridge.bind_earning(
            record, job, ledger, fx_rate=FX_TRY_TO_USDC, payer_signer=employer_key)
        claim = binding.claim

        # a) pactiva-bloğu-silinirse → 6-RED
        c1 = {k: v for k, v in binding.charge.items() if k != "pactiva"}
        v1 = PactaEscrowBridge.verify_binding(c1, claim)
        assert v1["verdict"] == "RED"
        assert v1["checks"]["6_pactiva_proof"] is False

        # b) earning_canon-tahrif edilirse → 7-RED ( hash-yeniden-üretmez)
        c2 = {k: (dict(v) if k == "pactiva" else v)
              for k, v in binding.charge.items()}
        c2["pactiva"]["earning_canon"] = {**c2["pactiva"]["earning_canon"],
                                          "gross_locked": "1.00"}
        v2 = PactaEscrowBridge.verify_binding(c2, claim)
        assert v2["verdict"] == "RED"
        assert v2["checks"]["7_earning_recomputes"] is False

        # c) expected_usdc-escrow-tutarıyla-çelişirse → 8-RED
        c3 = {k: (dict(v) if k == "pactiva" else v)
              for k, v in binding.charge.items()}
        c3["pactiva"]["expected_usdc"] = "1.000000"
        v3 = PactaEscrowBridge.verify_binding(c3, claim)
        assert v3["verdict"] == "RED"
        assert v3["checks"]["8_escrow_reconcile"] is False
