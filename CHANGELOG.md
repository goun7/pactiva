# Changelog

## [Unreleased]

### [Fix-2026-10-05] — Pacta escrow mesh bağı
- Eklendi: [`pactiva_core/pacta_escrow.py`](pactiva_core/pacta_escrow.py) —
  hak-ediş kayıtlarını ( emanet-kasası → `release_escrow_payout` →
  Proof-of-Audit-mührü) GERÇEK Pacta `EscrowJob`/`SettlementBinder` modeline
  bağlar ve Tamga D5 hash-chain'ine sabitler ( RFC-010 additive; şema
  değişikliği yok). RFC-010 beş kontrolü + pactiva üçü ( 6/7/8), fail-closed.
- Eklendi: `tests/test_pacta_escrow.py` ( 5 test) — yeşil-yol, tutar-uyuşmazlığı
  RED, disbursed-olmayan RED, TRY-için-kur-zorunlu ( fail-closed), tahrif-
  edilmiş-charge yakımı. Toplam 104 → 109 test.
- Dürüst-sınır: Pactiva-hak-edişi-TRY / Pacta-escrow-USDC; kuru-çağıran-sağlar
  ve-charge'a-yazar, kur-yoksa-köprü-RED-verir ( machine-checkable-değil).

## [0.1.0] — 2026-09-24
- İlk genel sürüm: Pactiva — Dağıtık İstihdam, Bilişsel Yetkinlik & Emanet Hak-Ediş Altyapısı
- Pactiva **fon yönetmez-AMA-hak-ediş-yönetir** — bilişsel-yetkinlik-

## Sürümleme

- [SemVer](https://semver.org/lang/tr/) uyumludur.
