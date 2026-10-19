# Pactiva — Dağıtık İstihdam, Bilişsel Yetkinlik & Emanet Hak-Ediş Altyapısı

> ⚠️ **DURUM ( 2026-09-29): RAFA KALDIRILDI — karar (C).**
> Çekirdek güven-iddiaları 2025–2026 akademik literatürü ile çelişmektedir. Detaylı dürüst
> değerlendirme ve gerekçe: [`docs/arastirma/degerlendirme-A-B-C.md`](docs/arastirma/degerlendirme-A-B-C.md).
> Akademik doğrulama: [`docs/arastirma/akademik-arastirma-2026.md`](docs/arastirma/akademik-arastirma-2026.md).
> **Bu repo referans/arşiv amaçlıdır; aktif geliştirme yapılmamaktadır.** Kod ve testler
> hala çalışır durumdadır ( 226 test yeşil, 0 failed rc=0 — LEED-ölçümü 2026-10-18) ama **üretim-dağıtımı-yapılmamalıdır**.

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
| §6-whitelist | RFC-010 §6.1-13-zincir-listesinde ( refere edilen
  `tools/settlement_bind_verify.py` bu-rafta-DEĞIL — mesh-kardeş-tarafta) |
| Tahkim-protokolü | `pactiva/v1` RFC-011-SUPPORTED_PROTOCOLS'te
  ( refere edilen `tools/dispute_pointer_verify.py` bu-rafta-DEĞIL) |

## Pacta escrow bağlantısı ( mesh)

`fon yönetmez-AMA-hak-ediş-yönetir` ilkesinin kodda gerçekleşimi:
[`pactiva_core/pacta_escrow.py`](pactiva_core/pacta_escrow.py). Bir serbest-
bırakılmış hak-ediş kaydını ( emanet-kasası → `release_escrow_payout` →
Proof-of-Audit-mührü) GERÇEK Pacta escrow modeline bağlar ve ortak sonucu
Tamga D5 hash-chain'ine sabitler ( README'nin §6-foreign_chain_proof çizgisi):

```
hak-ediş ( disbursed + audit-block-hash)
  → earning_hash      ( sha256/jcs — bağımsız yeniden-üretilebilir)
  → EscrowJob SETTLED ( Pacta) ↔ tutar/parti/sonuç uzlaşı
  → D5 charge + imzalı claim  ( RFC-010 additive — şema değişikliği YOK)
```

Üretilen charge RFC-010'ın beş kontrolünü geçen bir **üstkümesidir** —
Pacta'nın kendi gate'i onu kabul eder; bunun üzerine pactiva-üçü ( 6/7/8)
eklenir: `pactiva-proof` ( disbursed + 64-hex audit-mührü), `earning-recomputes`
( hash baştan hesaplanır, Pactiva'nın sözüne güvenilmez), `escrow-reconcile`
( ödene değer ↔ escrow tutarı + taraflar). İlk RED'de tümü RED ( fail-closed)
ve hiçbir şey zincire yazılmaz. Değer-transferi YOK — bağ taahhüdü sabitler.

> ⚠️ **Para-birimi ( dürüst):** Pactiva-hak-edişi **TRY**, Pacta-escrow'u
> **USDC**. TRY→USDC-kuru dış-piyasa-verisidir-ve-machine-checkable-DEĞİLDİR;
> bu-yüzden-kuru-çağıran-sağlar-ve-charge'a-yazar. Kur-verilmezse-köprü-RED-
> verir — belirsiz-değeri-escrow'a-sabitlemek-yanlış-kanıt-üretirdi.

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

## Akademik Kaynaklar ( 2024-2026)

Bu-çalışma aşağıdaki araştırmaya dayanır ( her referans canlı
doğrulanmıştır):

- **[1] Dinamik-katılım-hissesi** —
  *Algorithmic Monetary Policies for Blockchain Participation Games* —
  Ferraioli et al., arXiv 2025.
  Ajanların **türü ( yetkinlik) + hissesi** ile karakterize edildiği,
  her turda **katılım veya çekilme** seçtiği tekrarlı-oyun modeli;
  politika yüksek-tür ajanları görev-yürütümü için seçerken ödülleri
  merkeziyetsizliği-sürdürmek için dağıtır. Doğrudan Pactiva'nın
  " yetkinlik + hisse → katılım → ödül" akışına karşılık gelir.
  [arXiv:2512.16514](https://arxiv.org/abs/2512.16514)
- **[2] Beceri-tabanlı-ödül-dağıtımı** —
  *SkillShapley: Boundary-Adaptive Shapley Valuation for Skill Step
  Attribution in LLM Agents* — Liu et al., arXiv 2026.
  Bir becerinin **her adımının genel-performansa katkısını** Shapley
  değeriyle nicelleştirir — " hangi adım ne kadar hak-etti?" sorusuna
  oyun-teorik cevap. Pactiva'nın beceri-tabanlı hak-ediş-skoru için
  dağıtım-adilliği yöntemidir.
  [arXiv:2608.13173](https://arxiv.org/abs/2608.13173)
- **[3] Bilişsel-yetkinlik-değerlendirmesi** —
  *Using profiles of cognitive capability to assess AI suitability for
  workplace tasks* — Prunty et al., arXiv 2026.
  Ajan ve görevleri **ortak bilişsel-yetkinlik profilleriyle** eşleştirir;
  toplu-benchmark-skorları yerine görev-bazlı yetkinlik-çıkarımı yapar.
  Pactiva'nın " bilişsel-yetkinlik-kanıtı" için ölçüm-yöntemidir.
  [arXiv:2608.25623](https://arxiv.org/abs/2608.25623)
- **[4] Hak-edişe-göre-paylaşım** —
  *Pool Formation in Oceanic Games: Shapley Value and Proportional
  Sharing* — Kiayias et al., arXiv 2025.
  Proof-of-Stake havuzları içinde üyeler arasında **katkıya-göre ödül
  bölme** mekanizmalarını inceler. Pactiva'nın emanet-hak-ediş
  dağıtımının oyun-teorik temelidir.
  [arXiv:2505.04422](https://arxiv.org/abs/2505.04422)
- **[5] Katkı-tabanlı-teşvik** —
  *Blockchain-based Framework for Scalable and Incentivized Federated
  Learning* — Wu et al., arXiv 2025.
  Zincir-üstü hizalama-tabanlı ödüller + zincir-dışı **adillik-denetimleri**
  + tutarlılık-çarpanları ile katkıyı ödüllendirir. Pactiva'nın
  Proof-of-Audit + hak-ediş-skoru düzeni için referans-mimari.
  [arXiv:2502.14170](https://arxiv.org/abs/2502.14170)
- **[6] İtibar-güven-modeli** —
  *A Sustainable and Reward Incentivized High-Performance Cluster
  Computing for Artificial Intelligence: A Novel Bayesian-Time-Decay
  Trust Mechanism in Blockchain* — Yaslioglu, arXiv 2025.
  **Bayesci-zaman-sönümlü güven** mekanizması ile ödül-hesabını
  zamanla-değerlendirir. Pactiva'nın meslektaş-itibarı ağı için
  sönümlü-güven modelidir.
  [arXiv:2511.21844](https://arxiv.org/abs/2511.21844)
- **[7] Katkı-kredi-atfı** —
  *MARS-RA: Rank Aggregation for Credit Assignment via Multimodal
  Comparisons in Embodied Multi-Agent Cooperation* — Wang et al., arXiv 2026.
  Kredi-atfını **mutlak değil göreceli** ( ikili-karşılaştırma + sıra-
  agregasyon) tahmin olarak yeniden-formüle eder; gecikmiş-geri-bildirim
  ve değişen-ajan-sayısı altında sağlamdır. Pactiva'nın kanıt-tabanlı
  hak-ediş-atfı için robustluk kaynağıdır.
  [arXiv:2607.27967](https://arxiv.org/abs/2607.27967)
