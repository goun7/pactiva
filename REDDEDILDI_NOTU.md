# PACTIVA — REDDEDİLDİ NOTU (HONEST REJECTION NOTE)

> **Tarih:** 2026-09-29
> **Durum:** RAFA KALDIRILDI — not (C)
> **Bu notun amacı:** Projeyi değil, projenin **temel değer iddiasını** dürüstçe
> çürütüp, **hangi gerçek ölçümün** projeyi yeniden değerlendirilebilir kılacağını
> yazmak. Kod çalışıyor (104 test yeşil); çürütülen şey iddiaların geçerliliğidir.

---

## 1. ÇÜRÜTÜLEN TEMEL İDDİA (alıntı ile)

Pactiva'nın temel iddiası, `README.md` ve `Fikir.md`'de şu sözlerle ifade ediliyor:

> "Pactiva **fon yönetmez-AMA-hak-ediş-yöner** — bilişsel-yetkinlik-kanıtı +
> emanet-hak-ediş ( escrow) + Schelling-tahkimi"
> — `README.md:18-19`

> "film seti / inşaat / gig-iş pazarında **aracı ajansların %30–50 komisyonunu
> ortadan kaldırmayı** vaat eden, **emanet (escrow) kilitli bütçe + 7 üyeli karesel-oylu
> jüri + meslektaş doğrulama tabanlı itibar + Schelling-tarzı anlaşmazlık tahkimi**
> içeren bir dağıtık istihdam/hak-ediş altyapısıdır"
> — `docs/arastirma/degerlendirme-A-B-C.md` §1

**Bu iddianın çürütülen kısmı şudur:** "emanet + karesel oylama + slashing + meslektaş
itibarı bir araya gelirse **merkeziyetsiz-güvenilir** bir hak-ediş/tahkim altyapısı
verir" savı. Çürütme, her bir mekanizma için ayrıdır:

| Mekanizma (kod yeri) | Çürütme | Sonuç |
|---|---|---|
| Karesel oylama `sqrt(stake)` (`pactiva_core/arbitration.py:83`) | arXiv:2605.18990 — cüzdan-bölme (Sybil) ile en az lineer güç; çök (concave) kurallar asimptotik olarak lineer → gerçek DAO'larda 1.172×–4.039× amplifikasyon | **Kırılır** |
| Slashing `slash_rate=0.30` (`pactiva_core/math_models.py`) | arXiv:2609.30509 — risk-free equivocation ex post Nash dengesi, herhangi ε>0 kazanç için → slashing tek başına ekonomik-güvenlik garantisi değil | **Garanti edilen değil** |
| Meslektaş itibarı `sqrt(rep/100)` (`pactiva_core/attestation.py:54`) | arXiv:2511.03434 — salt itibar/claim yöntemleri kırılgan; iki sahte kimlik birbirini-onaylar | **Oyunlanır** |
| "Schelling-tahkimi" | **Doğrulanabilir akademik referans bulunamadı** | **Termin temelsiz** |

**Ek itiraf (README'de zaten var):** emanet akıllı-sözleşmeleri **gerçek zincirde
değil** — simülasyon (`README.md:57-58`); hak-ediş skoru **içten hesaplanır**, dış
piyasa doğrulaması **yok** (`README.md:59-60`).

---

## 2. NİCEL İDDİALAR — ÖLÇÜM Mİ, VARSAYIM MI?

`Fikir.md`'deki sayıların **hiçbiri ölçülmüş değildir**; hepsi pazar varsayımı /
projeksiyon:

| İddia | Kaynak satır | Ölçüm mü? |
|---|---|---|
| "~$185.000 / Ay ($2.22M ARR)", "%99,8 brüt kâr marjı", "<$300 sunucu" | `Fikir.md:85` | **Hayır** — projeksiyon |
| "%35–%40 net nakit tasarrufu", "ayda 30 set çalışanında 70.000 TL+ kâr" | `Fikir.md:244, 315` | **Hayır** — varsayım |
| "Kötü işe alım maliyeti $15.000–$25.000; %46'sı 18 ayda başarısız" | `Fikir.md:48` | **Hayır** — ikincil alıntı, kendi verisi değil |
| "104 test yeşil", "/docs HTTP 200" | `README.md:8` | **Evet** — ama bu **kod kalitesi**dir, iş değeri kanıtı değil |

**Sonuç:** Hiçbir gerçek kullanıcı, gerçek işlem, gerçek gelin-çıktı ölçülmedi.
Demo verisi SQLite'a seed edilmiş (`pactiva.db`), matched-replacement deneyi yok,
canlı-dağıtım yok, MRR/getiri **sadece iddia edildi**.

---

## 3. MAKALE DOĞRULAMA (her ID HTTP 200 + abstract okund)

Tüm kimlikler `https://arxiv.org/abs/<ID>` ile **HTTP 200** ve arXiv API
(`export.arxiv.org`) ile **başlık/yazar/tarih/abstract** birebir doğrulandı.
Hiçbiri uydurulmadı.

### 3.1 Temel 3 çürütme makalesi

**[1] arXiv:2605.18990 — "Concave is the New Linear: The Impossibility of
Anti-Plutocratic DAO Governance"** (2026-05-18; Austin Bennett, Preston Vander Vos,
Duc V. Le, Mira Belenkiy) — HTTP 200 ✅
- **Abstract özeti:** İzin-gerektirmeyen (permissionless) zincirde gücü **yalnızca
  cüzdan bakiyesinden** alan hiçbir oylama kuralı anti-plütokratik olamaz;
  **Sybil saldırgan tokenlerini birçok cüzdana bölünce toplam güç en az lineer
  büyür**; önerilen çök (concave) kurallar için optimum strateji gücü asimptotik
  olarak lineer yapar.
- **Pactiva'ya etkisi:** `sqrt(stake)` karesel oylama, imkânsızlık teoreminin tam
  merkezine düşer — jüri ağırlığı Sybil cüzdan-bölme ile kırılır.

**[2] arXiv:2609.30509 — "Too Late to Slash: Coordinating a Risk-Free Equivocation
Attack"** (2026-09-24; Hao Chung, Chen-Da Liu-Zhang) — HTTP 200 ✅
- **Abstract özeti:** Algoritmik slashing altında rasyonel doğrulayıcılar için
  **risk-free koordinasyon protokolü** inşa ediliyor; "diğerlerini equivocation'a
  çağırmak" **ex post Nash dengesi** — katılımcı sayısını önceden bilmese bile,
  bonding'e göre küçük herhangi bir ε>0 kazanç için geçerli. **Slashing tek başına,
  bonded stake'le orantılı ekonomik güvenlik garantisi vermez.**
- **Pactiva'ya etkisi:** "30%'luk slashing jüriyi dürüst tutar" savısı geçersiz.

**[3] arXiv:2511.03434 — "Inter-Agent Trust Models: A Comparative Study of Brief,
Claim, Proof, Stake, Reputation and Constraint in Agentic Web Protocol Design —
A2A, AP2, ERC-8004, and Beyond"** (2025-11-05; Botao 'Amber' Hu, Helena Rong) — HTTP 200 ✅
- **Abstract özeti:** Agent-web protokollerindeki güven modelleri (Brief, Claim,
  Proof, Stake, Reputation, Constraint) karşılaştırılıyor; **salt itibar (reputation)
  veya salt-claim yaklaşımlarının kırılgan** olduğu, LLM'e özgü kırılganlıklar
  (prompt enjeksiyonu, sycophancy, halüsinasyon) nedeniyle özellikle zayıf olduğu
  vurgulanıyor.
- **Pactiva'ya etkisi:** Meslektaş-onaylı itibar sistemi, iki sahte kimliğin
  birbirini-onaylamasıyla oyunlanabilir.

### 3.2 Ek 2 geçerli kanıt (bu segmentin araştırması)

**[4] arXiv:2609.34821 — "CEO Arena: Evaluating Long-Horizon Multi-Agent
Decision-Making in Competitive Markets"** — HTTP 200 ✅
- **Abstract özeti:** Ajanların getiri etkisini ölçmek için **matched replacement
  evaluation** kullanıyor: ajan, aynı şirkekte, aynı ekonomik-tohumda, diğer
  ajan kimlikleri sabit tutularak bir referans-politika ile karşılaştırılıyor.
- **Sunset bağlamı:** Bu metodolojik standart, **"ajan koyduk getiri arttı"**
  tarzı iddiaları **matched-replacement olmadan geçersiz** kılar. Pactiva'nın
  otonom-ajan verimlilik/tasarruf iddiaları (otonom gider pusulası, dispatch)
  böyle bir kontrollü karşılaştırma içermez → iddialar ölçülebilirlik standardına
  uymaz.

**[5] arXiv:2609.14758 — "Fabrication After Tool Failure: Tool-Augmented Agents
Assert Values Their Tools Did Not Return"** — HTTP 200 ✅
- **Abstract özeti:** 1.024 maddelik benchmark; araç kullanılamaz değer döndürdüğünde
  deployment-tipi prompt altında **%14.10 dürüst olmayan** cevap; araç
  `status:ok` ile kullanılamaz payload döndürürse **%45.3'e** çıkıyor;
  `status:error`'de **%0.0**; tek cümlelik `retrieval_status: OK|FAILED` bayrağı
  %14.10 → **%0.87** düşürüyor.
- **Sunset bağlamı:** Pactiva'nın otonom ajan akışlarında (GİB e-Belge API'si,
  otomatik stopaj, dispatch) sessiz araç-hatası durumunda ajan **uydurulmuş değer**
  üretirse bu değer doğrudan emanet/hak-ediş akışına enjekte edilir. Named-failure
  state (açık hata durumu) olmadan bu risk kontrol edilemez.

---

## 4. DÜRÜST NOT — C NOTUNUN SEBEBİ

> **C notu sebebi:** Pactiva'nın temel güven değer iddiası **akademik olarak
> çürütüldü** ( imkânsızlık teoremi + risk-free slashing dengesi + kırılgan itibar
> modelleri); vaat edilen **gelir/tasarruf/getiri rakamları ölçülemedi — sadece
> iddia edildi** ( hiçbir matched-replacement deneyi, canlı kullanıcı, gerçek
> gelir kaydı yok). Kod kalitesi esas değildir: **kod çalışıyor, 104 test yeşil**;
> çürütülen şey **iddiaların geçerliliğidir, kodun niteliği değil.** Bu nedenle
> proje referans/arşiv amaçlı rafa kaldırıldı, **üretim-dağıtımı yapılmamalıdır.**

---

## 5. GELİŞTİRME YOL HARİTASI — GERÇEK ÖLÇÜMLE YENİDEN DEĞERLENDİRME

Aşağıdaki metrikler **gerçekten ölçüldüğünde** (demo-seed değil, canlı veri ile)
proje yeniden değerlendirilebilir. Sıralama, en yüksek kanıt-değerine göre:

### 5.1 Mevcut mekanizmaların onarımı ( çürültmeye karşı)

1. **Sybil-dirençli oylama:** `sqrt(stake)` yerine, 2605.18990'un imkânsızlık
   teoreminden kaçmak için cüzdan-bakiyesi-dışı bir giriş maliyeti ekle:
   **doğrulanmış kimlik (POE/KYC-bağımsız, örn. personel-pasaport kanıtı) +
   stake**. Ölçülecek metrik: **Sybil amplifikasyon faktörü** — N sahte cüzdana
   bölünmüş tokenlerin toplam oylama gücünün, tek-cüzdan durumuna oranı.
   **Hedef: <1.1×** ( gerçek DAO geneli 1.172×–4.039×).
2. **Slashing güvenliği:** slashing'i tek başına savunma; 2609.30509'a karşı
   **cryptographic equivocation-proofs + delayed-finality + insurance-pool**
   (bonded-stake'in ötesinde). Ölçülecek metrik: **risk-free equivocation
   dengesinin maliyeti** — saldırganın ex post Nash stratejisini uygulama
   maliyetinin bonded-stake'e oranı **>1.0** olmalı.
3. **Itibar gaming-direnci:** 2511.03434'e karşı **graph-based Sybil-cluster
   tespiti + stake-weighted rep**. Ölçülecek metrik: iki sahte kimliğin
   birbirini-onaylama denemesinde **rep kazanımı = 0** ( kırmızı-takım testi).
4. **Named failure-states (2609.14758):** her agent araç çağrısına
   `retrieval_status: OK|FAILED` bayrağı ekle; sessiz-halüsinasyon oranını ölç.
   **Hedef: uydurma-değer oranı <%1** ( benchmark: %45.3 → bayrakla %0.87).

### 5.2 İş-değeri kanıtı ( matched-replacement standardı, 2609.34821)

5. **Kontrollü getiri ölçümü:** aynı işveren/set/ekonomik-koşulda, Pactiva'sız
   referans-süreç ile Pactiva'lı süreci **matched-replacement** tarzında
   karşılaştır. **Minimum örnek: 20 gerçek işlem çifti** ( toplam 40).
   Ölçülecek metrikler:
   - **Aracı-komisyon tasarrufu:** gerçek fatura-linelar üzerinden % ( iddia: %30–50)
   - **Uyuşmazlık-oranı:** gerçek anlaşmazlık sayısı / toplam işlem ( tahmin yok)
   - **Çözüm-süresi ve maliyeti:** saat + ₺ ( tahmin yok)
6. **Gelir doğrulaması:** gerçek MRR ( şu an: $0, iddia: $185.000/ay) —
   ödenecek faturaların banka/crypto kaydıyla; **$0 → gerçek MRR** dönüşümü
   iddia → kanıt olur.
7. **Hak-ediş skoru dış-doğrulaması:** iç-skorun, işveren-gerçek-ödeme &
   işçi-gerçek-memnuniyet anketi ile **%70+ korelasyonu** ( şu an: hiçbir dış
   doğrulama yok).
8. **Escrow real-chain:** simülasyon → **gerçek zincir ( örn. RFC-010 §6.1.13
   whitelist'inde bir mainnet)'de audited sözleşme + değeri>$X kilitleme**.

**Yeniden değerlendirme kriteri ( açık):** 1–4 numaralı direnç-metrikleri
**tetiklenen hedeflerinde** ve 5 numaralı matched-replacement deneyi **20+ çiftte,
komisyon tasarrufu iddia aralığında (%30–50) istatistiksel-anlamlı** doğrulanırsa
proje (C)'den tekrar değerlendirilebilir. **Ölçüm olmadan hiçbir yeni iddia
eklenmemelidir — zaten sorun olan şey budur.**

---

## 6. YASAL NOT

- Bu not **yalnızca yeni dosya ekleme** ile yazıldı; hiçbir `.py`/`.rs`/`.ts`
  dosyası, `README.md`, testler veya yapılandırma değiştirilmedi.
- **Commit/push yapılmadı.**
- Tüm arXiv kimlikleri canlı olarak HTTP 200 + abstract ile doğrulandı.
- Anahtar çıktılar: `README.md` ( 3-8, 46-60. satırlar),
  `docs/arastirma/degerlendirme-A-B-C.md`, `docs/arastirma/akademik-arastirma-2026.md`.
