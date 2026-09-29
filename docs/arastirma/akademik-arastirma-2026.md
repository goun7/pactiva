# Pactiva — Akademik Araştırma Raporu (2025–2026)

> **Tarih:** 2026-09-29
> **Amaç:** Pactiva'nın çalıştığı alanda **güncel, gerçek akademik makaleleri** tespit etmek ve
> projenin temel mekanizmalarını (karesel oylama, Schelling tahkimi, slashing, emanet, itibar)
> bu literatüre karşı **dürüst** olarak değerlendirmek.
>
> **Doğrulama yöntemi:** Aşağıdaki **her bir** arXiv kimliği `web_fetch` ile birebir açılmış,
> başlık/yazar/tarih/özet metinleri canlı kaynaktan okunmuştur. **Hiçbir kaynak uydurulmamıştır.**
> Doğrulanamayan veya bulunamayan konular bölüm sonunda açıkça belirtilmiştir.

---

## 1. Pactiva'nın temel mekanizmaları (kısa bağlam)

Pactiva'nın çekirdeği dört mekanizmaya dayanır:

1. **Karesel oylama (Quadratic Voting)** — jüri ağırlığı `sqrt(stake_amount)`
   (`pactiva_core/arbitration.py:83`).
2. **Schelling konsensüsü + slashing** — jüriler `worker_favor / employer_favor / split` oyler;
   konsensüsten sapanlar `slash_rate=0.30` oranınca kesilir (math_models.py).
3. **Meslektaş doğrulama (peer attestation) + itibar** — ağırlık `sqrt(rep/100)`
   (`pactiva_core/attestation.py:54`), HMAC imzalı.
4. **Emanet (escrow)** — kilitli bütçe + hak-ediş serbest bırakma (README'e göre
   **simülasyon** sözleşmeleri, gerçek zincirde değil).

Bu rapor, her birini literatüre karşı test eder.

---

## 2. Doğrulanmış makaleler

### 2.1 Karesel oylama — destekleyici

**[1] arXiv:2504.12859** — *"Enhancing Decentralization in Blockchain Decision-Making Through
Quadratic Voting and Its Generalization"*
- **Yazarlar:** Lyudmila Kovalchuk, Mariia Rodinko, Roman Oliynykov, Andrii Nastenko,
  Dmytro Kaidalov, Kenric Nelson
- **Tarih:** 17 Nisan 2025 · **Alan:** cs.GT
- **Doğrulama:** `https://arxiv.org/abs/2504.12859` fetch ile birebir açıldı ✓
- **Bulgular:** Üç QV tipi tanımlanıyor: Type 1 (toplam stake'e sqrt, sonra dağıt),
  **Type 2 (önce dağıt, sonra sqrt)**, Type 3 (ayrıştırmadan). Type 2 ve 3'ün **Gini ve
  Nakamoto katsayılarıyla ölçülen merkeziyetsizliği iyileştirdiği** resmen ispatlanıyor.
- **Pactiva'ya etkisi:** **Destekleyici.** Pactiva'nın `sqrt(stake)` yaklaşımı bu
  sınıflandırma içinde Type 2/3 ailesine girer ve merkeziyetsizlik amacı akademik olarak
  haklıdır. **Ancak** makale, hangi QV tipinin kullanıldığının split-direnci açısından
  kritik olduğunu vurguluyor — Pactiva bu ayrımı belgelememiştir.

### 2.2 Karesel oylama — ELEŞTİREL (en önemli bulgu)

**[2] arXiv:2605.18990** — *"Concave is the New Linear: The Impossibility of Anti-Plutocratic
DAO Governance"*
- **Yazarlar:** Austin Bennett, Preston Vander Vos, Duc V. Le, Mira Belenkiy
- **Tarih:** 18 Mayıs 2026 · **Alan:** cs.GT
- **Doğrulama:** `https://arxiv.org/abs/2605.18990` fetch ile birebir açıldı ✓
- **Bulgular:** **İmkânsızlık teoremi.** İzin-gereksiz (permissionless) bir blokzincirde
  sadece cüzdan bakiyesinden güç türeten **hiçbir** oylama kuralı başarılı olamaz.
  Costs modellemesi (cüzdan bölme maliyeti, sabit kurulum maliyeti, minimum-bakiye)
  içinde, **büyüklüğü ne olursa olsun bir cüzdan sıfır-olmayan güç veriyorsa, bir Sybil
  saldırganı tokenlerini birçok cüzdana bölerek toplam gücünü token tutusuyla en az
  lineer büyütebilir.** Konkav (sqrt gibi) kurallarda optimal strateji asimptotik olarak
  lineer güç verir. Gerçek DAO'lar (ENS, Compound, Uniswap, Arbitrum, ZKsync) üzerinde
  replay edilen önerilerde **Quadratic Voting altında Sybil amplifikasyon faktörü
  1.172× ile 4.039×** ölçülmüş; daha dik kurallarda 229.000×'i aşmış.
- **Pactiva'ya etkisi:** **DOĞRUDAN VE CİDDİ ELEŞTİRİ.** Pactiva'nın jüri ağırlığı
  `sqrt(stake_amount)` tam olarak bu makalenin eleştirdiği konkav kural ailesidir.
  Pactiva'da jüriye **Sybil direnci sağlayan bir mekanizma yoktur**: `cast_juror_vote`
  sadece `stake_amount > 0` kontrol eder; bir saldırgan tek bir büyük stake'i bin küçük
  juror kimliğine bölerek **toplam karesel ağırlığı ~√1000 ≈ 31× büyütebilir**.
  Pactiva'nın "7 üyeli bağımsız jüri" iddiası, kimlik-benzersizliği (identity uniqueness)
  olmadan bu saldırıya karşı savunmasızdır. **Bu, düzeltilmesi gereken bir tasarım boşluğudur.**

### 2.3 Slashing — ELEŞTİREL

**[3] arXiv:2609.30509** — *"Too Late to Slash: Coordinating a Risk-Free Equivocation Attack"*
- **Yazarlar:** Hao Chung, Chen-Da Liu-Zhang · **Tarih:** 24 Eylül 2026 · **Alan:** cs.GT
- **Doğrulama:** `https://arxiv.org/abs/2609.30509` fetch ile birebir açıldı ✓
- **Bulgular:** Slashing'in PoS blokzincirlerini güvence altına aldığı argümanı **heristiktir,
  resmi bir oyun-teororik garanti değildir.** Makale, rasyonel validatorler için **risk-free
  bir koordinasyon protokolü** inşa ediyor: diğerlerini equivocation'a davet etmek
  stratejisinin **ex post Nash dengesi** olduğunu, validatorler önceden kaç kişinin
  katılacağını bilmese bile geçerli olduğunu gösteriyor. Bu, bonded stake'ten bağımsız
  **herhangi** bir ε > 0 kazanç için geçerli. **Sonuç: slashing tek başına, bonded stake
  değeriyle orantılı ekonomik güvenlik garanti ETMEZ.** Algoritmik slashing, saldırganların
  kontrol ettiği aynı konsensüs sürecine bağımlıdır; gerçek dünyadaki rehin-collateral
  düzenlemeleri gibi dış yaptırıma (mahkemeler) güvenemez.
- **Pactiva'ya etkisi:** **DOĞRUDAN VE CİDDİ ELEŞTİRİ.** Pactiva'nın tüm jüri-ödül
  tasarımı "honest behavior pays, slashing punishes" varsayımına dayanır
  (`resolve_dispute`'taki `slash_rate=0.30`). Bu makale, benzer bir mekanizmanın
  **koordinasyonlu bir saldırıya karşı risk-free olduğunu** kanıtlıyor. Pactiva'da
  jüriler arasında koordinasyon (özel iletişim, rüşvet) engellenmiyor. Yani:
  **Pactiva'nın slashing'i hile yapan jürileri caydırmak için yeterli bir garanti
  olarak sunulamaz.** En azından Pactiva'nın bunu resmi bir güvenlik modeliyle
  değerlendirmesi gerekir.

### 2.4 Davranış-tabanlı alternatif (yapıcı yön)

**[4] arXiv:2506.22171** — *"Proof-of-Behavior: Behavior-Driven Consensus for Trustworthy
Decentralized Finance"*
- **Yazarlar:** Ailiya Borjigin, Wei Zhou, Cong He · **Tarih:** 27 Haziran 2025
- **Alan:** cs.DC (WI IAT 2025'e gönderildi)
- **Doğrulama:** `https://arxiv.org/abs/2506.22171` fetch ile birebir açıldı ✓
- **Bulgular:** Her aksiyona katmanlı fayda skoru (motivasyon + sonuç) veren **Proof-of-
  Behavior (PoB)** konsensüs modeli; validator ağırlıkları son skorlerle adapte oluyor ve
  **orantılı slashing** uygulanıyor. Ödül tasarımı incentive-compatible: **dürüst davranış
  uzun-vadeli kazancı maksimize eden Nash dengesi** veriyor. Simüle edilmiş DeFi
  deneylerinde dolandırıcılık-kabulünü **%90'dan fazla** azaltıyor, kötü validatorleri
  **iki tur içinde** düşürüyor, standart PoS'tan daha adil proposer adaleti sağlıyor
  (throughput overhead'i %5'i geçmiyor).
- **Pactiva'ya etkisi:** **Yapıcı bir alternatif.** Pactiva'nın "itibar + slashing"
  kombinasyonu PoB ile aynı yöndedir, ama PoB **resmi bir Nash-dengesi ispatı** ve
  orantılı-adaptasyon sunuyor. Pactiva, jüri davranış geçmişini itibarına yansıtan ve
  bunu resmi olarak modelleyen bir mekanizmaya doğru evrilebilir. Somut, kanıtlanmış bir
  yöntem referansıdır.

### 2.5 Güven modelleri — Proof / Stake / Reputation karşılaştırması

**[5] arXiv:2511.03434** — *"Inter-Agent Trust Models: A Comparative Study of Brief, Claim,
Proof, Stake, Reputation and Constraint in Agentic Web Protocol Design"*
- **Yazarlar:** Botao 'Amber' Hu, Helena Rong · **Tarih:** 5 Kasım 2025 · **Alan:** cs.HC
  (AAAI 2026 TrustAgent Workshop'a gönderildi)
- **Doğrulama:** `https://arxiv.org/abs/2511.03434` fetch ile birebir açıldı ✓
- **Bulgular:** **Brief / Claim / Proof / Stake / Reputation / Constraint** güven
  modellerini karşılaştırıyor; her birinin varsayım, saldırı yüzeyi ve tasarım
  ödünleşimlerini analiz ediyor. **"Hiçbir tek mekanizma yeterli değildir"** sonucuna
  varıyor: Proof ve Stake ile "trustless-by-default" mimariyi öneriyor, Reputation'ı
  esneklik/sosyal sinyal için bir katman olarak kullanıyor. Özellikle **reputation gaming,
  Sybil, collusion, whitewashing** direncini değerlendiriyor.
- **Pactiva'ya etkisi:** **Doğrudan ilgili.** Pactiva'nın meslektaş-doğrulama sistemi
  saf bir **Reputation** modelidir (HMAC imzalı atıflar + karesel itibar ağırlığı). Bu
  makale, salt reputation yaklaşımının **reputation-gaming'e kırılgan** olduğunu
  sınıflandırıyor. Pactiva'da bir çalışan, sahte işveren/iş kimlikleri oluşturup
  karşılıklı atıf yaparak `cumulative_trust_weight`'i şişirebilir — çünkü `create_peer_attestation`
  sadece `worker_id != endorser_id` kontrol eder (self-endorsement engeli), **iki ayrı
  sahte kimliğin birbirini onaylamasını** engellemez. Bu makale bunun bilinen bir
  zayıflık sınıfı olduğunu kanıtlıyor.

### 2.6 İş-pazarekonomisi (gig/labour)

**[6] arXiv:2512.04988** — *"When AI Agents Compete for Jobs: Strategic Capabilities and
Economic Dynamics of AI Labour Markets"*
- **Yazarlar:** Christopher Chiu, Simpson Zhang, Mihaela van der Schaar
- **Tarih:** 4 Aralık 2025 (ICML 2026'da kabul edildi)
- **Doğrulama:** arXiv Atom API sorgusu ile tam metadata döndü ✓
- **Bulgular:** LLM ajanlarının iş için yarıştığı simüle edilmiş bir gig economy
  (`AI-Work`); **adverse selection ve reputation dynamics** gibi iş-pazarekonomisi
  güçlerini inceliyor. Metakognisyon, rekabet farkındalığı ve uzun-horizon stratejik
  planlama yeteneğine sahip ajanların tutarlı olarak daha yüksek kâr ve pazar payı
  elde ettiğini gösteriyor.
- **Pactiva'ya etkisi:** **Kısmen ilgili.** Pactiva'nın "bilişsel yetkinlik kanıtı +
  hak-ediş skoru" fikri, iş-pazarekonomisinin **adverse selection** problemine
  işaret ediyor — bu mekanizmanın çözmeye çalıştığı gerçek ekonomik problem. Ancak
  Pactiva'nın kanıtı **içsel olarak hesaplanır** (README itiraf ediyor: "dış-piyasa
  doğrulaması YOK"), yani adverse selection'ı dışsallıkten dolayı kapatmaz.

---

## 3. Doğrulanamayan / bulunamayan konular (dürüst itiraf)

Aşağıdaki konularda **hiçbir doğrulanmış akademik kaynak sağlayamadım**. Bunları
**uydurmuyorum**; yok olarak işaretliyorum:

| Aranan konu | Sonuç | Not |
|---|---|---|
| **Schelling noktası tabanlı blokzincir tahkimi** üzerine akademik makale | **Bulunamadı** | `abs:Schelling AND abs:blockchain` arXiv sorgusu **0 sonuç** döndü. "Schelling court / Kleros-tarzı tahkim" kavramı arXiv'de doğrulanabilir bir makale olarak bulunamadı. Pactiva'nın "Schelling-tahkimi" terimine akademik bir referans **sağlayamıyorum**. |
| **Merkeziyetsiz tahkim/decentralized arbitration** üzerine güçlü makale | **Bulunamadı** | `abs:"decentralized arbitration"` sorgusu yalnızca 1 sonuç döndü: 2022 tarihli bir NFT hırsızlık-mekanizması makalesi (arXiv:2208.05168) ki bu Pactiva'nın alanı değil, **ilgisiz**. |
| **Schelling oyunu**nun token-tahkimde uygulanmasının resmi analizi | **Bulunamadı** | Kavram oyun-teorisinde bilinir (Schelling 1960), ama blokzincir tahkimine uygulayan doğrulanabilir bir 2025–2026 makalesi bulamadım. |
| **Escrow / emanet** akıllı-sözleşme güvenliği üzerine spesifik makale | **Bulunamadı** | Pactiva'nın emaneti zaten **simülasyon** (README itiraf ediyor), bu yüzden akademik bir dayanak aramak çok anlamlı değil. |
| **4857/4904/GVK94** (Türk İş Kanunu / Borçlar Kanunu) akademik kaynak | **Bulunamadı** | Türk mevzuatıdır; uluslararası akademik makale değil, yasa metnidir. Doğrulanabilir bir akademik referans değil. |

---

## 4. Literatüre göre Pactiva değerlendirmesi (dürüst)

### Güçlü (literatür tarafından desteklenen yanlar)
1. **Karesel oylamanın merkeziyetsizlik amacı haklı** — [1] QV'nin Gini/Nakamoto
   katsayılarını iyileştirdiğini resmen ispatlıyor. Pactiva'nın yönelimi yanlış değil.
2. **"Reputation + slashing" genel yönelimi bilinen bir tasarım ailesi** — [4], [5]
   bunun çalışılan, sınıflandırılmış bir güven-modeli ailesi olduğunu gösteriyor.
3. **Adverse selection gerçek bir problem** — [6] iş-pazarlarında reputation dynamics'in
   merkezi olduğunu kanıtlıyor; Pactiva'nın çözmeye çalıştığı problem gerçek.

### Zayıf / Ciddi (literatürün çürüttüğü yanlar)
1. **Sybil saldırısına karşı savunmasız (EN CİDDİ)** — [2] `sqrt(stake)` gibi konkav
   kuralların cüzdan-bölme ile kırıldığını **resmi bir imkânsızlık teoremi** ile kanıtlıyor
   (gerçek DAO'larda 1.172×–4.039× amplifikasyon). Pactiva'da jüri kimlik-benzersizliği
   **yok**. "7 üyeli bağımsız jüri" iddiası bu saldırı karşısında geçersizdir.
2. **Slashing bir güvenlik garantisi olarak sunulamaz** — [3] koordinasyonlu equivocation
   saldırısının **risk-free ex post Nash dengesi** olduğunu kanıtlıyor. Pactiva'nın
   "hile yapan kesilir" varsayımı resmi olarak temelsizdir.
3. **Reputation gaming engellenmiyor** — [5] salt reputation modellerinin kırılganlığını
   sınıflandırıyor. Pactiva'da iki sahte kimlik birbirini onaylayabilir; sadece
   self-endorsement (aynı kimlik) engelli. `verified_peer_badge` (≥2 atıf) bu
   saldırıyla kolayca alınabilir.
4. **"Schelling-tahkimi" için akademik dayanak yok** — doğrulanabilir bir referans
   **sağlayamadım** (yukarıdaki tablo). Bu terim iç pazarlama dilidir; akademik bir
   ağırlığı yoktur.
5. **Mevzuat iddiaları akademik değildir** — 4857/4904/GVK94 yasa metinleridir;
   doğrulanmış akademik kaynak olarak sunulamazlar.

### Sonuç
Pactiva'nın **çözmeye çalıştığı problem gerçek** (gig-pazarında aracı sömürüsü, adverse
selection) ve **kodlama kalitesi yüksektir** (gerçek SQLite, HMAC imza, quadratic-voting
mantığı). Ancak **üç temel güvenlik mekanizmasının da (QV, slashing, reputation) 2025–2026
literatürü tarafından çürütülen veya sınırlandırılan varsayımları** vardır:
- QV → Sybil kırığı ([2])
- Slashing → güvenlik garantisi değil ([3])
- Reputation → gaming kırığı ([5])

Proje, bu üç zayıflığı **gidermeden** "güvenli/dezentralize hak-ediş altyapısı" olarak
sunulamaz. **"Schelling" ve "decentralized arbitration" iddialarının akademik bir
dayanağını tespit edemedim** — bu, dürüst iletişimde belirtilmelidir.
