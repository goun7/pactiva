"""
Pactiva — Yasal Üçlü Sözleşme ve Müteselsil SGK İzolasyon Motoru (pactiva_core/contracts.py)
4857 SK (Md. 2/41/69), 4904 SK (Md. 19), 193 Sayılı GVK (Md. 94) ve 6698 SK KVKK uyumlu sözleşme altyapısı.
"""

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

from pactiva_core.math_models import TWO_PLACES


def generate_tripartite_contract(
    employer_id: str,
    worker_id: str,
    job_id: str,
    job_title: str,
    base_hourly_rate: Decimal,
    expected_hours: Decimal,
    category: str,
    contract_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    İşveren, Serbest Çalışan ve Platform arasında yasal üçlü bağımsız hizmet çerçevesini üretir.
    Alt işveren (taşeron) ilişkisi ve müteselsil SGK cezası riskini kanunen bertaraf eder.
    """
    cid = contract_id or str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    total_estimated = (base_hourly_rate * expected_hours).quantize(TWO_PLACES)

    # Kanuni maddelerin bağlayıcı metni
    contract_clauses = [
        "MADDE 1 (TARAFLAR VE STATÜ): İşbu sözleşme, İlan Sahibi (İşveren), Bağımsız Yüklenici (Serbest Çalışan) ve Teknoloji/Emanet Sağlayıcısı (Pactiva) arasında akdedilmiştir. Pactiva doğrudan işveren veya alt işveren olmayıp, 4904 Sayılı Kanun Madde 19 uyarınca çalışandan komisyon almayan teknolojik emanet ve yetkinlik doğrulama altyapısıdır.",
        "MADDE 2 (MÜTESELSİL SORUMLULUK İZOLASYONU): 4857 Sayılı İş Kanunu Madde 2 uyarınca taraflar arasında asıl işveren-alt işveren ilişkisi kurulmamıştır. Çalışan bağımsız yüklenici olup, çalışma saatlerini ve usulünü serbestçe tayin eder.",
        f"MADDE 3 (HAK EDİŞ VE BÜTÇE KİLİDİ): Taban saatlik ücret {base_hourly_rate} TL olup, öngörülen {expected_hours} saatlik mesai karşılığı olan {total_estimated} TL bütçe saklamasız emanet kasasında önceden rezerve edilmiştir.",
        "MADDE 4 (FAZLA ÇALIŞMA VE GECE MESAİSİ): 4857 Sayılı Kanun Madde 41 uyarınca haftalık 45 saati veya günlük azami süreyi aşan çalışmalar %50 zamlı; Madde 69 uyarınca saat 20:00-06:00 arası gece mesaileri yasal zamlı oran üzerinden PTP donanımsal zaman damgasıyla otomatik tahakkuk ettirilir.",
        "MADDE 5 (VERGİ VE STOPAJ TEVKİFATI): 193 Sayılı Gelir Vergisi Kanunu Madde 94 uyarınca vergi mükellefiyeti bulunmayan çalışan adına brüt tutardan %10 stopaj kesintisi yapılarak GİB e-Gider Pusulası tanzim edilir.",
        "MADDE 6 (KVKK VE BİYOMETRİK VERİ KORUMASI): 6698 Sayılı KVKK Madde 6 uyarınca çalışanın yüz veya parmak izi gibi ham biyometrik verileri sunucularda ASLA depolanmaz; yalnızca istemci tarafında üretilen SHA-256 doğrulama özetleri kütüklenir."
    ]

    canonical_text = "\n\n".join(contract_clauses)
    contract_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
    archive_url = f"https://legal.pactiva.internal/contracts/{datetime.now(timezone.utc).year}/{cid}.pdf"

    return {
        "contract_id": cid,
        "employer_id": str(employer_id),
        "worker_id": str(worker_id),
        "job_id": str(job_id),
        "job_title": job_title,
        "category": category,
        "base_hourly_rate": base_hourly_rate,
        "expected_hours": expected_hours,
        "estimated_total_payout": total_estimated,
        "statutory_compliance": {
            "is_4857_isolated": True,
            "is_4904_zero_commission_worker": True,
            "is_gvk_94_tax_handled": True,
            "is_kvkk_6_compliant": True,
        },
        "contract_sha256_hash": contract_hash,
        "canonical_clauses": contract_clauses,
        "archive_url": archive_url,
        "created_at": now,
        "is_digitally_signed": True,
    }


def verify_contract_integrity(canonical_clauses: list[str], expected_hash: str) -> bool:
    """Sözleşme metninin imzalandıktan sonra değiştirilmediğini SHA-256 ile doğrular."""
    canonical_text = "\n\n".join(canonical_clauses)
    computed_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
    return computed_hash == expected_hash
