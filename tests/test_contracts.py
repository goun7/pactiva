"""
Pactiva Yasal Üçlü Sözleşme ve SGK İzolasyonu Testleri (tests/test_contracts.py)
"""

from decimal import Decimal
from uuid import uuid4
import pytest

from pactiva_core.contracts import generate_tripartite_contract, verify_contract_integrity


def test_tripartite_contract_statutory_compliance():
    employer_id = str(uuid4())
    worker_id = str(uuid4())
    job_id = str(uuid4())

    contract = generate_tripartite_contract(
        employer_id=employer_id,
        worker_id=worker_id,
        job_id=job_id,
        job_title="Set Işık Şefi (Gece Çekimi)",
        base_hourly_rate=Decimal("450.00"),
        expected_hours=Decimal("10.0"),
        category="film_set",
    )

    # 450 * 10 = 4500.00 TL
    assert contract["estimated_total_payout"] == Decimal("4500.00")
    assert contract["statutory_compliance"]["is_4857_isolated"] is True
    assert contract["statutory_compliance"]["is_4904_zero_commission_worker"] is True
    assert contract["statutory_compliance"]["is_gvk_94_tax_handled"] is True
    assert contract["statutory_compliance"]["is_kvkk_6_compliant"] is True
    assert len(contract["contract_sha256_hash"]) == 64
    assert len(contract["canonical_clauses"]) == 6


def test_contract_integrity_verification():
    contract = generate_tripartite_contract(
        employer_id=str(uuid4()),
        worker_id=str(uuid4()),
        job_id=str(uuid4()),
        job_title="Kule Vinç Operatörü",
        base_hourly_rate=Decimal("400.00"),
        expected_hours=Decimal("8.0"),
        category="construction",
    )

    clauses = contract["canonical_clauses"]
    valid_hash = contract["contract_sha256_hash"]
    assert verify_contract_integrity(clauses, valid_hash) is True

    # Manipüle edilmiş metin reddedilmeli
    tampered = list(clauses)
    tampered[0] = tampered[0] + " (sahte ekleme)"
    assert verify_contract_integrity(tampered, valid_hash) is False
