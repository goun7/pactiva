# Pactiva — Dağıtık İstihdam, Bilişsel Yetkinlik & Emanet Hak-Ediş Altyapısı

> ⚠️ **DURUM ( 2026-09-29): RAFA KALDIRILDI — karar (C).**
> Çekirdek güven-iddiaları 2025–2026 akademik literatürü ile çelişmektedir. Detaylı dürüst
> değerlendirme ve gerekçe: [`docs/arastirma/degerlendirme-A-B-C.md`](docs/arastirma/degerlendirme-A-B-C.md).
> Akademik doğrulama: [`docs/arastirma/akademik-arastirma-2026.md`](docs/arastirma/akademik-arastirma-2026.md).
> **Bu repo referans/arşiv amaçlıdır; aktif geliştirme yapılmamaktadır.** Kod ve testler
> hala çalışır durumdadır ( 104 test yeşil) ama **üretim-dağıtımı-yapılmamalıdır**.

> **Ana-belge:** [`Fikir.md`](Fikir.md) — master-teknik-şartname
> ( Proje-22 + Proje-37'nin-tek-kurumsal-mimaride-birleşimi).
> **Bu-README-hızlı-başlangıç-içindir; ayrıntılar-ana-belgede.**
> **Tasarım-kökleri:** [`docs/kok-fikir-22.md`](docs/kok-fikir-22.md),
> [`docs/kok-fikir-37.md`](docs/kok-fikir-37.md)

## Rolü ( TAMGA-MESH-içinde)

Pactiva **fon yönetmez-AMA-hak-ediş-yönetir** — bilişsel-yetkinlik-
kanıtı + emanet-hak-ediş ( escrow) + Schelling-tahkimi:

```
yetkinlik-kanıtı → Proof-of-Audit → hak-ediş-skoru
        ↓ ( kanıt-hash'i)
   §6-foreign_chain_proof → tamga D5-ledger ( RFC-010 §6: pactiva-kendi-adında)
        ↓
   anlaşmazlık → Schelling-tahkimi ( RFC-011: pacta/v1-protokolü)
```

## Güvenlik-modeli ( AT-141..161-§6-dikişleri + AT-087)

| Özellik | Uygulama |
|---|---|
| §6-head | Proof-of-Audit-kökü; `evidence_link`-ile-bağlı |
| Kanıt-adı | `pactiva`-kendi-adında ( AT-107/134-dersi) |
| §6-whitelist | RFC-010 §6.1-13-zincir-listesinde ( tools/settlement_bind_verify.py) |
| Tahkim-protokolü | `pactiva/v1` RFC-011-SUPPORTED_PROTOCOLS'te
  ( tools/dispute_pointer_verify.py:27 — AT-187-doğrulaması) |

## Çalıştırma

```bash
docker compose up -d    # docker-compose.yml + Dockerfile
python3 -m pytest tests/ -q
```

## Sınırlar ( dürüst)

- ⚠️ **PROJE RAFA KALDIRILDI** — aşağıdaki iddiaların **akademik olarak geçerliliği yoktur**:
  - **Karesel oylama** ( `sqrt(stake)`): Sybil cüzdan-bölme saldırısıyla kırılır
    ( arXiv:2605.18990, imkânsızlık teoremi; gerçek DAO'larda 1.172×–4.039× amplifikasyon).
  - **Slashing**: tek başına ekonomik-güvenlik garantisi değildir
    ( arXiv:2609.30509, risk-free equivocation Nash dengesi).
  - **Meslektaş-itibarı**: iki sahte kimliğin birbirini-onaylamasıyla-oyunlanır
    ( arXiv:2511.03434, reputation-gaming).
  - **"Schelling-tahkimi"**: bu-termin için **doğrulanabilir akademik bir referans
    bulunamamıştır**.
- ** Emanet-akıllı-sözleşmeler-gerçek-zincirde-DEĞİL** — simülasyon-
  sözleşmeleri ( docs/ESLESTIRME_CORE.md); üretim-dağıtımı-öncesi.
- ** Hak-ediş-skoru-iç-olarak-hesaplanır**; dış-piyasa-doğrulaması-YOK
  ( Proof-of-Audit-mechanizması-üzerinden-güvenilir)
