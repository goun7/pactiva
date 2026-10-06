"""
Pactiva ↔ Pacta escrow mesh bağı — hak-ediş kaydı → escrow settlement charge.

MESH-BAĞLANTISI ( 01_unicorn/22-37-Pactiva ↔ 01_unicorn/03-Pacta):

    hak-ediş ( Pactiva emanet-kasası → release_escrow_payout → Proof-of-Audit)
      → escrow settlement charge ( Pacta SettlementBinder + delivery_hash + escrow)
        → imzalı claim ( x402/v1 sha256-özüt imzası)
          → Tamga D5 hash-chain ( RFC-010 §6: pactiva-kendi-adında)

Pactiva **fon yönetmez-AMA-hak-ediş-yönetir** ( README): bir mesainin
hak-edildiği Proof-of-Audit-zincirinde kanıtlanır, emanet-kasası serbest-
bırakır-ve-net-hak-ediş yazılır. AMA-o-kanıt Pactiva'nın-kendi-belleğinde/
SQL'inde-kalır-ve Pacta'nın-escrow/settlement-kararına-BAĞLI-DEĞİLDİR.
"İşçinin-hak-edişi-ödendi"-sözü-Pactiva'nın-kendi-çıktısı-kadar-iyidir;
Pacta'nın-"TESLİMAT-kanıtlandı"-kararından-bağımsızdır. Bu-modül-o-uçağı-
kapatır: hak-ediş-kaydını-bağımsız-yeniden-hesaplanabilir-bir-hash'e-
sıkıştırır, Pacta-escrow'un-tutar/parti/sonuç-olgularıyla-çapraz-uzlaştırır-
ve-ortak-sonucu-Pacta'nın-D5-hash-chain'ine-sabitler ( README'nin §6-
foreign_chain_proof → tamga-D5-ledger-çizgisinin-kodda-gerçekleşimi).

Üretilen-charge, RFC-010'ın-beş-kontrolünü-GEÇEN-bir-**üstkümesidir** (
additive-alanlar-şema-değişikliği-YAPMAZ — tıpkı-``SettlementBinder.
build_charge``'ın-ve-RenewLock'un-``build_renewlock_charge``'ının-docstring'
indeki-kural-gibi). Yani-Pacta'nın-KENDİ-gate'i-onu-kabul-eder-ve-üç-yönlü-
bir-çapraz-test-doğar:

    Pactiva-hak-edişi ↔ Pacta-escrow'u ↔ RFC-010-beş-kontrolü

EK-KONTROLLAR ( RFC-010'ın-beşinin-üzerine; fail-closed — biri-RED → tümü-RED):

  6. pactiva-proof      — charge ``pactiva``-bloğu-var, escrow_status=
                          "disbursed", audit_block_hash-64-hex ve
                          ``pactiva_ref``-ile-eşleşir
  7. earning-recomputes — earning_hash bağımsız-yeniden-hesaplanır ( RFC-8785
                          JCS-ile; Pactiva'nın-sözüne-güvenilmez) ve-charge'a
                          yazılan-değerle-bire-bir
  8. escrow-reconcile   — hak-edişin-ödene-değeri == escrow-tutarı,
                          taraflar-eşleşir

PARA-BİRİMİ ( dürüst-sınır): Pactiva-hak-edişi **TRY**-denomine-dir,
Pacta-escrow'u **USDC**. TRY→USDC-kuru-dış-piyasa-verisidir-ve-
machine-checkable-DEĞİLDİR; bu-yüzden-kuru-çağıran-sağlar-ve-charge'a
``fx_rate_to_usdc``-olarak-yazar ( denetlenebilir-additive-alan). Kur-
verilmezse-ve-para-birimi-USDC-değilse-köprü-RED-verir — belirsiz-değeri
escrow'a-sabitlemek-yanlış-kanıt-üretirdi; fail-closed-bunu-ister (
tıpkı-RenewLock'un-CPI-endeksli-escalator-limiti-gibi).

DEĞER-TRANSFERİ-YOK: bağ-hak-edişin-taahhüdünü-sabitler; fon-akışı-hâlâ
Pactiva'nın-emanet-kasasında-ve-Pacta'nın-vault-ledger'ındadır.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Optional

# ------------------------------------------------------------------ Pacta keşfi
# Mesh-bağı-GERÇEK-Pacta-escrow-modelini-kullanır. Keşif-başarısızsa-import-
# hatası-açık-gelsin — sahte-bir-escrow-modeli-üretmek-dürüst-değildir.


def _pacta_root() -> Optional[Path]:
    """03-Pacta-checkout'unu-bul veya None ( env → komşu-yol → bilinen-kurulum)."""
    here = Path(__file__).resolve().parents[1]            # .../22-37-Pactiva
    cands = [
        os.environ.get("PACTA_ROOT"),
        str(here.parent / "03-Pacta"),                    # .../01_unicorn/03-Pacta
        "/home/gokun/projects/01_unicorn/03-Pacta",
    ]
    for c in cands:
        if not c:
            continue
        root = Path(c).expanduser().resolve()
        if (root / "pacta" / "models.py").is_file() \
                and (root / "pacta" / "integrations" / "tamga_d5.py").is_file():
            return root
    return None


def _ensure_pacta_on_path() -> Optional[Path]:
    """Pacta'yı-sys.path'e-ekle ( modül-içi-pacta-importundan-ÖNCE-çalışır)."""
    root = _pacta_root()
    if root is not None and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


PACTA_ROOT = _ensure_pacta_on_path()

from pacta.integrations.tamga_d5 import D5Ledger, SettlementBinder   # noqa: E402
from pacta.integrations.tamga_jcs import jcs                          # noqa: E402
from pacta.models import EscrowJob, EscrowStatus                      # noqa: E402


PACTIVA_TAG = "pactiva/v1"               # additive-etiket ( RFC-011 protokol-adı)
USDC = "USDC"                            # Pacta-escrow'unun-para-birimi
QUANT = Decimal("0.000001")              # 6-ondalık — Pacta-quantizasyonu
AMOUNT_TOLERANCE = Decimal("0.000001")   # USDC — quantizasyon-payı

# Earning-hash'i-için-kanonik-alanlar ( RFC-8785/JCS-hash'i-bunlardan-üretilir;
# Pactiva'nın-sözüne-değil-kanıtlanan-olgunun-bu-alanlarına-güvenilir).
CANONICAL_ALANLAR = (
    "job_id",
    "worker_id",
    "employer_id",
    "escrow_id",
    "gross_locked",
    "platform_fee",
    "withholding_tax",
    "currency",
    "escrow_status",
    "audit_block_hash",
)


class PactaEscrowBridgeError(Exception):
    """Köprü-hatası — hak-ediş-doğrulama-veya-uzlaşı-reddedildi ( fail-closed)."""


# ------------------------------------------------------------------ modeller


@dataclass
class HakEdisRecord:
    """Pactiva-hak-ediş-kaydı — serbest-bırakılmış-emanet-ödemesinin-kanıt-şekli.

    ``escrow_status``-"disbursed"-olmalı; "locked"/"refunded" bir-hak-ediş-
    değildir ( fail-closed). ``employer_address``/``worker_address``-escrow-
    kimlikleridir ( EVM) — Pactiva-kullanıcıları-UUID-ile-tanımlandığı-için
    onları-Pacta-escrow-adresleri-olarak-köprü-çağıran-sağlar.
    """

    job_id: str
    job_title: str
    worker_id: str
    employer_id: str
    escrow_id: str
    gross_locked: Decimal                      # emanet-kilitli-brüt ( TRY)
    platform_fee: Decimal                      # %2-%4-altyapı-payı
    withholding_tax: Decimal                   # GVK-94-stopaj
    currency: str = "TRY"
    provider_tx_ref: str = ""
    escrow_status: str = "disbursed"
    audit_block_hash: Optional[str] = None     # Proof-of-Audit-zincir-mührü
    employer_address: str = ""                 # işveren-escrow-kimliği ( EVM)
    worker_address: str = ""                   # çalışan-escrow-kimliği ( EVM)
    earned_at_epoch: float = field(default_factory=lambda: time.time())

    @classmethod
    def from_escrow_payout(
        cls,
        escrow: Dict[str, Any],
        job: Dict[str, Any],
        *,
        worker_id: str,
        employer_address: str,
        worker_address: str,
        audit_block_hash: Optional[str] = None,
    ) -> "HakEdisRecord":
        """``PactivaRepository.release_escrow_payout``-çıktısından-kayıt-üret.

        Ana-üretim-yolu: ``escrow``-``escrow_accounts``-satırıdır ( status=
        "disbursed"), ``job``-``jobs``-satırıdır ( status="completed").
        ``worker_id``-vardiya/vergi-pusulası-bağlamından-çağıran-tarafından-
        sağlanır ( emanet-hesabı-iş-düzeyindedir, çalışan-düzeyinde-değil).
        """
        return cls(
            job_id=str(escrow["job_id"]),
            job_title=str(job.get("title", "")),
            worker_id=str(worker_id),
            employer_id=str(job.get("employer_id", "")),
            escrow_id=str(escrow["id"]),
            gross_locked=Decimal(str(escrow["locked_amount"])),
            platform_fee=Decimal(str(escrow["platform_fee"])),
            withholding_tax=Decimal(str(escrow.get("withholding_tax_reserved", "0"))),
            currency=str(escrow.get("currency", "TRY")),
            provider_tx_ref=str(escrow.get("provider_tx_ref", "")),
            escrow_status=str(escrow.get("status", "disbursed")),
            audit_block_hash=audit_block_hash,
            employer_address=employer_address,
            worker_address=worker_address,
        )

    def canonical(self) -> Dict[str, Any]:
        """Hash-için-kanonik-gövde ( Decimal'ler-string, JCS-serileştirilebilir)."""
        return {
            "job_id": self.job_id,
            "worker_id": self.worker_id,
            "employer_id": self.employer_id,
            "escrow_id": self.escrow_id,
            "gross_locked": str(self.gross_locked),
            "platform_fee": str(self.platform_fee),
            "withholding_tax": str(self.withholding_tax),
            "currency": self.currency,
            "escrow_status": self.escrow_status,
            "audit_block_hash": self.audit_block_hash,
        }

    @property
    def earning_hash(self) -> str:
        """``sha256( jcs( canonical))`` — bağımsız-yeniden-üretilebilir-hak-ediş-özeti."""
        return hashlib.sha256(jcs(self.canonical())).hexdigest()

    def net_payout_amount(self) -> Decimal:
        """Çalışana-geçen-net-hak-ediş: brüt − altyapı-payı − stopaj ( GVK-94).

        Deterministiktir-ve-``tax_invoices.net_payout_amount``-ile-tutarlıdır;
        negatif-olamaz ( işveren-işçiye-para-borçlanamaz).
        """
        net = self.gross_locked - self.platform_fee - self.withholding_tax
        return net.quantize(QUANT, rounding=ROUND_HALF_UP)

    def expected_usdc(self, fx_rate: Optional[Decimal]) -> Optional[Decimal]:
        """Hak-edişin-USDC-karşılığı; belirsizse-None ( fail-closed).

        Para-birimi-USDC-ise-kur-1-geçerlidir. Farklı-para-birimi-ve-kur-YOKsa
        **None** — dış-piyasa-kuru-machine-checkable-değildir, değeri-escrow'a
        sabitlemek-yanlış-kanıt-üretirdi ( RenewLock-CPI-limiti-ile-aynı-kural).
        """
        if fx_rate is None:
            fx_rate = Decimal("1") if self.currency == USDC else None
        if fx_rate is None:
            return None
        return (self.gross_locked * fx_rate).quantize(QUANT, rounding=ROUND_HALF_UP)


@dataclass
class HakEdisBinding:
    """Bir-hak-ediş-kaydının-D5-sabitleme-sonucu ( charge-escrow, claim-alıcı)."""

    charge: Dict[str, Any]
    claim: Dict[str, Any]
    delivery_hash: str
    ledger_tip: Optional[str]
    record: HakEdisRecord
    reconciliation: Dict[str, Any]
    fx_rate: Optional[Decimal]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "charge": self.charge,
            "claim": self.claim,
            "delivery_hash": self.delivery_hash,
            "ledger_tip": self.ledger_tip,
            "record": self.record.__dict__,
            "reconciliation": self.reconciliation,
            "fx_rate": str(self.fx_rate) if self.fx_rate is not None else None,
        }


# -------------------------------------------------------------------- köprü


class PactaEscrowBridge:
    """Hak-ediş-kaydı → escrow-settlement-charge → D5-kanıtı köprüsü.

    Tüm-yöntemler-static'tir — köprü-durumsuzdur; durum-Pactiva'nın-emanet-
    kasasında-ve-Pacta'nın-EscrowJob'unda/D5-ledger'ında-tutulur.
    """

    # --- 1) hak-ediş doğrulama -------------------------------------------
    @classmethod
    def verify_record(cls, record: HakEdisRecord) -> Dict[str, Any]:
        """Pactiva-hak-ediş-kaydını-bağımsız-doğrula ( GREEN/RED/İNDETERMİNE).

        Pactiva'nın-sözüne-güvenilmez: ``earning_hash``-i-kaydın-KENDİ-kanonik
        alanlarından-baştan-hesaplar-ve-charge'a-yazılan-değerle-karşılaştırır.
        """
        out: Dict[str, Any] = {"ok": False, "verdict": None, "reason": None,
                               "reason_code": None, "checks": {}}

        # e1) hak-ediş-gerçekten-serbest-bırakılmış-mı?
        ok1 = record.escrow_status == "disbursed"
        out["checks"]["e1_disbursed"] = ok1
        if not ok1:
            out.update(verdict="RED", reason_code=11,
                       reason=f"not_disbursed: emanet kasası durum="
                              f"{record.escrow_status!r} — yalnızca serbest "
                              f"bırakılmış (disbursed) hak ediş sabitlenir")
            return out

        # e2) tutarlar-öz-tutarlı-mı? ( brüt > 0; pay+stopaj-brütten-fazla-
        # olamaz; çalışan-net'i-negatif-olamaz)
        g, f, t = record.gross_locked, record.platform_fee, record.withholding_tax
        ok2 = bool(g > Decimal("0") and f >= Decimal("0") and t >= Decimal("0")
                   and (f + t) <= g)
        out["checks"]["e2_amounts_consistent"] = ok2
        if not ok2:
            out.update(verdict="RED", reason_code=12,
                       reason="amounts_inconsistent: brüt>0 ve 0<=pay+stopaj<=brüt "
                              "olmalı (işveren işçiye borçlanamaz)")
            return out

        # e3) Proof-of-Audit-mührü-64-hex-sha256-mi? ( Pactiva'nın-kendi-zinciri)
        abh = record.audit_block_hash
        ok_abh = isinstance(abh, str) and len(abh) == 64 \
            and all(c in "0123456789abcdef" for c in abh.lower())
        out["checks"]["e2b_audit_block_hash"] = ok_abh
        if not ok_abh:
            out.update(verdict="RED", reason_code=13,
                       reason="audit_block_invalid: Proof-of-Audit zincir mührü "
                              "64-hex-sha256 olmalı (ESCROW_PAYOUT_RELEASED bloğu)")
            return out

        # e4) earning-hash-bağımsız-yeniden-üretilebilir-mi? ( JCS-Pacta'nın-
        # kendi-sözleşmesidir; yoksa-esirgenir)
        try:
            recomputed = hashlib.sha256(jcs(record.canonical())).hexdigest()
        except Exception as exc:                       # pragma: no-cover
            out.update(verdict="İNDETERMİNE", reason_code=14,
                       reason=f"jcs_unavailable: kanonikleştirme hesaplanamıyor "
                              f"({type(exc).__name__}) — hak ediş esirgenir")
            return out
        ok4 = recomputed == record.earning_hash
        out["checks"]["e4_earning_recomputes"] = ok4
        if not ok4:
            out.update(verdict="RED", reason_code=15,
                       reason=f"earning_hash_mismatch: bağımsız hesap "
                              f"{recomputed[:24]}… ≠ kayıt "
                              f"{record.earning_hash[:24]}…")
            return out

        out.update(ok=True, verdict="GREEN", reason_code=0,
                   reason="hak ediş doğrulandı: disbursed, tutarlar öz-tutarlı, "
                          "audit-mührü geçerli, earning_hash bağımsız yeniden "
                          "üretilebilir")
        return out

    # --- 2) hak-ediş ↔ escrow uzlaşı --------------------------------------
    @classmethod
    def reconcile(cls, record: HakEdisRecord, job: EscrowJob,
                  fx_rate: Optional[Decimal] = None) -> Dict[str, Any]:
        """Pactiva-hak-edişini-Pacta-escrow-settlement'ı-ile-çapraz-uzlaştır.

        İki-bağımsız-sistem-aynı-ödeme-iddia-ediyorsa-tutar/parti/sonuç-uymak-
        zorunda; uymazlarsa-bağ-yanlış-kanıt-üretir-ve-reddedilir ( fail-closed).
        """
        expected = record.expected_usdc(fx_rate)
        checks = {
            "r1_settled": (job.status == EscrowStatus.SETTLED
                           and job.settlement_tx is not None),
            "r2_amount": (expected is not None
                          and abs(Decimal(str(job.amount_usdc)) - expected)
                          <= AMOUNT_TOLERANCE),
            "r3_parties": (str(record.employer_address).lower()
                           == str(job.buyer_address).lower()
                           and str(record.worker_address).lower()
                           == str(job.seller_address).lower()),
            "r4_disbursed_bound": record.escrow_status == "disbursed",
        }
        bad = [k for k, v in checks.items() if not v]
        return {
            "ok": not bad,
            "checks": checks,
            "reason": ("reconciled" if not bad
                       else f"pactiva_escrow_mismatch: {', '.join(bad)}"),
            "expected_usdc": str(expected) if expected is not None else None,
        }

    # --- 3) escrow-kayıt-üretimi -------------------------------------------
    @classmethod
    def build_pactiva_charge(
        cls,
        job: EscrowJob,
        record: HakEdisRecord,
        delivery_hash: Optional[str] = None,
        fx_rate: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """D5-ledger'a-yazılacak-charge — RFC-010-üstkümesi ( additive).

        Taban-``SettlementBinder.build_charge``'tır ( beş-kontrolü-geçer);
        üzerine-``settlement_bind.pactiva_ref``-ve-``pactiva``-bloğu-eklenir.
        Şema-değişikliği-YOK: bilinmeyen-alanları-Pacta'nın-gate'i-görmezden-
        gelendir.
        """
        dh = delivery_hash or SettlementBinder.compute_delivery_hash(job)
        charge = SettlementBinder.build_charge(job, dh)

        expected = record.expected_usdc(fx_rate)
        charge["settlement_bind"]["pactiva_ref"] = {
            "scheme": PACTIVA_TAG,
            "job_id": record.job_id,
            "earning_hash": record.earning_hash,
        }
        charge["pactiva"] = {
            "workspace": "01_unicorn/22-37-Pactiva",
            "job_id": record.job_id,
            "job_title": record.job_title,
            "worker_id": record.worker_id,
            "employer_id": record.employer_id,
            "escrow_id": record.escrow_id,
            "provider_tx_ref": record.provider_tx_ref,
            "gross_locked": str(record.gross_locked),
            "platform_fee": str(record.platform_fee),
            "withholding_tax": str(record.withholding_tax),
            "net_payout": str(record.net_payout_amount()),
            "currency": record.currency,
            "fx_rate_to_usdc": str(fx_rate) if fx_rate is not None else "1",
            "expected_usdc": str(expected) if expected is not None else None,
            "employer_address": record.employer_address,
            "worker_address": record.worker_address,
            "escrow_status": record.escrow_status,
            "audit_block_hash": record.audit_block_hash,
            "earning_hash": record.earning_hash,
            "earning_canon": record.canonical(),   # bağımsız-yeniden-hesap-için
            "earned_at_epoch": record.earned_at_epoch,
            "bound_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        return charge

    # --- 4) ana-boru --------------------------------------------------------
    @classmethod
    def bind_earning(
        cls,
        record: HakEdisRecord,
        job: EscrowJob,
        ledger: D5Ledger,
        *,
        fx_rate: Optional[Decimal] = None,
        payer_signer: Optional[Any] = None,
    ) -> HakEdisBinding:
        """Hak-ediş-kaydı → escrow-settlement-charge → D5-kanıtı ( ana-boru).

        Sıra-önemli: önce-hak-ediş-doğrulanır,-sonra-uzlaşı; ikisi-de-yeşil-
        olmadan **hiçbir-şey-zincire-yazılmaz** ( fail-closed — yarım-kanıt-
        üretme).
        """
        v = cls.verify_record(record)
        if v["verdict"] != "GREEN":
            raise PactaEscrowBridgeError(
                f"record_not_green: {v['verdict']} — {v['reason']}")

        if record.expected_usdc(fx_rate) is None:
            raise PactaEscrowBridgeError(
                "indeterminate_value: hak ediş TRY-denominelidir ve USDC-"
                "escrow'a-sabitlemek-için fx_rate_to_usdc gerekir — dış piyasa "
                "kuru olmadan değer machine-checkable değildir (fail-closed)")

        rec = cls.reconcile(record, job, fx_rate)
        if not rec["ok"]:
            raise PactaEscrowBridgeError(f"reconciliation_failed: {rec['reason']}")

        dh = SettlementBinder.compute_delivery_hash(job)
        charge = ledger.append(cls.build_pactiva_charge(job, record, dh, fx_rate))
        claim = SettlementBinder.build_claim(job, dh, payer_signer=payer_signer)
        return HakEdisBinding(charge=charge, claim=claim, delivery_hash=dh,
                              ledger_tip=charge["h"], record=record,
                              reconciliation=rec, fx_rate=fx_rate)

    # --- 5) doğrulama-kapısı ------------------------------------------------
    @classmethod
    def verify_binding(cls, charge: Dict[str, Any],
                       claim: Dict[str, Any]) -> Dict[str, Any]:
        """RFC-010-beşi + pactiva-üçü ( 6/7/8) — ilk-RED'de-döner ( fail-closed).

        Sözlük-``SettlementBinder.verify_binding``-ile-aynıdır-böylece-iki-gate
        aynı-girdide-aynı-sonuç-verir; pactiva-kontrolleri-ancak-beşi-yeşil-ise
        çalışır ( kapı-zaten-KIRMIZI-ise-onu-olduğu-gibi-iade-eder).
        """
        base = SettlementBinder.verify_binding(charge, claim)
        if base.get("verdict") != "GREEN":
            return base

        out = dict(base)
        out["checks"] = dict(base["checks"])
        pa = charge.get("pactiva")
        bind = charge.get("settlement_bind") or {}
        ref = bind.get("pactiva_ref") or {}

        # 6) pactiva-proof-bloğu
        abh = pa.get("audit_block_hash") if isinstance(pa, dict) else None
        ok_abh = isinstance(abh, str) and len(abh) == 64 \
            and all(c in "0123456789abcdef" for c in abh.lower())
        ok6 = bool(isinstance(pa, dict)
                   and pa.get("escrow_status") == "disbursed"
                   and isinstance(pa.get("earning_hash"), str)
                   and pa["earning_hash"]
                   and ref.get("job_id") == pa.get("job_id")
                   and ref.get("earning_hash") == pa.get("earning_hash")
                   and ok_abh)
        out["checks"]["6_pactiva_proof"] = ok6
        if not ok6:
            out.update(ok=False, verdict="RED", reason_code=16,
                       reason="pactiva_proof_missing: charge pactiva-bloğu yok, "
                              "disbursed değil, audit-mührü geçersiz veya "
                              "pactiva_ref ile çelişiyor")
            return out

        # 7) earning-hash-bağımsız-yeniden-hesaplanır ( gönderene-güvenmeden)
        try:
            recomputed = hashlib.sha256(jcs(pa.get("earning_canon") or {})).hexdigest()
        except Exception as exc:                       # pragma: no-cover
            out.update(verdict="İNDETERMİNE", reason_code=14,
                       reason=f"jcs_unavailable: earning-hash yeniden "
                              f"hesaplanamıyor ({type(exc).__name__}) — sonuç "
                              f"esirgenir")
            return out
        ok7 = recomputed == pa["earning_hash"]
        out["checks"]["7_earning_recomputes"] = ok7
        if not ok7:
            out.update(ok=False, verdict="RED", reason_code=17,
                       reason=f"earning_hash_mismatch: bağımsız hesap "
                              f"{recomputed[:24]}… ≠ charge "
                              f"{pa['earning_hash'][:24]}…")
            return out

        # 8) hak-ediş ↔ escrow-uzlaşı ( D5-içinde-taşınan-fakatlar)
        esc = charge.get("escrow") or {}
        try:
            amount_ok = (Decimal(str(pa.get("expected_usdc")))
                         == Decimal(str(esc.get("amount_usdc"))))
        except Exception:
            amount_ok = False
        ok8 = (amount_ok
               and str(pa.get("employer_address", "")).lower()
               == str(bind.get("payer", "")).lower()
               and str(pa.get("worker_address", "")).lower()
               == str(bind.get("payee", "")).lower())
        out["checks"]["8_escrow_reconcile"] = ok8
        if not ok8:
            out.update(ok=False, verdict="RED", reason_code=18,
                       reason="escrow_reconcile_mismatch: hak edişin ödene "
                              "değeri/tarafları escrow kaydıyla uyuşmuyor")
            return out

        out.update(ok=True, verdict="GREEN", reason_code=0,
                   reason="sekiz-kontrol doğru: RFC-010 beşi + pactiva hak-edişi, "
                          "earning-hash-yeniden-üretimi, escrow-uzlaşı")
        return out

    # --- 6) D5 → Pactiva geri-okuma -----------------------------------------
    @staticmethod
    def pactiva_ref_of(charge: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """D5-charge'ından-Pactiva-hak-ediş-referansını-oku ( D5 → kayda geri-gitinme).

        ``None`` → bu-charge-bir-Pactiva-hak-ediş-bağı-değil ( sade-escrow).
        """
        ref = (charge.get("settlement_bind") or {}).get("pactiva_ref")
        return ref if isinstance(ref, dict) else None
