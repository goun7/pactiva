# Pactiva — Dağıtık İstihdam, Bilişsel Yetkinlik & Emanet Hak-Ediş Altyapısı

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
| Schelling-tahkimi | RFC-011-yoluyla-pacta-escrow'a-bağlanır ( bu-protokol-
  RFC-011'in-arbitration-protokol-listesinde-henüz-AYRICA-listelenmedi —
  SONRA-adımı: `pacta/v1`-listesine-eklenmesi; §4-WHAT-NEXT) |

## Çalıştırma

```bash
docker compose up -d    # docker-compose.yml + Dockerfile
python3 -m pytest tests/ -q
```

## Sınırlar ( dürüst)

- ** Emanet-akıllı-sözleşmeler-gerçek-zincirde-DEĞİL** — simülasyon-
  sözleşmeleri ( docs/ESLESTIRME_CORE.md); üretim-dağıtımı-öncesi
- ** Hak-ediş-skoru-iç-olarak-hesaplanır**; dış-piyasa-doğrulaması-YOK
  ( Proof-of-Audit-mechanizması-üzerinden-güvenilir)
