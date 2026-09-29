# Pactiva — Dürüst Değerlendirme ve Geliştirme Planı

> **Tarih:** 2026-09-29
> **Karar verici kriter:** Proje, gerçek bir teknik hendeğe (moat) sahip mi, yoksa temel
> iddiaları çürütülmüş bir fikir mi?

---

## KARAR: **(C) RAFA KALDIR** 🛑

> **Önemli not:** Bu karar **kod kalitesi hakkında değil**. Kod **gerçek ve çalışıyor**.
> Karar, projenin **temel değer iddiasının** (dezentrelize-güvenilir emanet/tahkim)
> **2025–2026 akademik literatürü tarafından çürütülmesi** hakkındadır. Aşağıda
> ayrıntılı gerekçe var.

---

## 1. Ne yapıyor (1 cümle)

Pactiva; film seti / inşaat / gig-iş pazarında **aracı ajansların %30–50 komisyonunu
ortadan kaldırmayı** vaat eden, **emanet (escrow) kilitli bütçe + 7 üyeli karesel-oylu
jüri + meslektaş doğrulama tabanlı itibar + Schelling-tarzı anlaşmazlık tahkimi** içeren
bir dağıtık istihdam/hak-ediş altyapısıdır.

## 2. KOD/TEST durumu

| Metrik | Değer | Kanıt |
|---|---|---|
| Python kaynak dosyası | 21 (`pactiva_core/*.py`), ~4.175 satır | `wc -l` |
| Test dosyası | 22 | `tests/` |
| **Test sonucu** | **104 passed, 0 failed (4.90s)** | `pytest tests/` çalıştırıldı |
| CLI komutu | 8 (status, lock-budget, release-escrow, generate-qr, dispatch, contract, audit-verify, erp-export) | `python3 pactiva --help` |
| REST API | FastAPI, `/docs` `HTTP 200`, health uç çalışıyor | uvicorn 8099'da çalıştırıldı |
| Web arayüz | var (`web/index.html` 486 satır + CSS 637 satır) | `web/` |
| **Demo alınabiliyor mu?** | **EVET** — emanet kilitleme/serbest-bırakma, jüri oylama, sözleşme SHA-256 tahrir-tespiti, güvenlik başlıkları çalışıyor | test dosyaları + API |
| Veritabanı | SQLite WAL, `schema.sql` ile 16+ tablo, gerçek FK emniyeti | `pactiva_core/database.py` |
| Bağımlılıklar | fastapi, uvicorn, pydantic — yüklü | import ile doğrulandı |

### Demo kanıtı (gerçek çalışma)
```
python3 pactiva status
→ Toplam Kayıtlı İlan : 164
  Aktif Kilitli İlan  : 101
  Sistem Durumu       : OPERATIONAL (SQLite WAL / REST API)

GET /api/v1/health → {"status":"operational","service":"Pactiva Core API","version":"1.0.0"}
GET /docs          → HTTP 200 (Swagger)
```

**Emanet yaşam-döngüsü testi** (`tests/test_escrow_lifecycle.py`) gerçek:
`locked → disbursed` (stopaj ayırma ile), `refund` (iptal), **tahrir edilmiş sözleşme**
için `is_valid: false / TAMPERED_BREACH`, güvenlik başlıkları (HSTS, X-Frame-Options).

## 3. "47 kod dosyası ama 3 commit" ne demek?

İlk commit `7ec46c6` **78 dosyayı tek seferde** (10.306 satır) eklemiş; sonraki 2 commit
**sadece README düzeltmesi**. Yani kod **başka yerde geliştirilip toplu kopyalanmış**.
Kanıt: commit mesajı "depo-başlatıldı", ve `docs/kok-fikir-22.md` içindeki kök yol
`/home/gokun/Masaüstü/Projeler/22OtonomİşİşçiBulma/` olarak geçiyor. Yani bu,
**Proje 22 + Proje 37'nin masaüstünden taşınmış birleşik kopyasıdır**, aşamalı
geliştirilmemiştir. Ayrıca `__pycache__/`, `.coverage`, `pactiva.db` (430 KB)
**commit'e dahil edilmiş** — git hijyeni kötü.

## 4. Akademik doğrulama özeti

Ayrıntılar: [`docs/arastirma/akademik-arastirma-2026.md`](arastirma/akademik-arastirma-2026.md)

**6 makale fetch ile doğrulandı.** Üçü **projenin temel mekanizmalarını çürütüyor**:

1. **arXiv:2605.18990** (May 2026) — **İmkânsızlık teoremi**: izin-gereksiz zincirde
   sadece cüzdan-bakiyesinden güç türeten **hiçbir** kural çalışamaz. Konkav (sqrt)
   kurallar **Sybil cüzdan-bölme ile kırılır**; gerçek DAO'larda **1.172×–4.039×**
   amplifikasyon ölçülmüş.
   → Pactiva'nın `sqrt(stake_amount)` jüri ağırlığı **tam bu saldırıya açık**;
   `cast_juror_vote` sadece `stake > 0` kontrol eder, **kimlik-benzersizliği yok**.
2. **arXiv:2609.30509** (Eyl 2026) — **Slashing güvenlik garantisi değildir**: koordinasyonlu
   equivocation saldırısı **risk-free ex post Nash dengesi**. Pactiva'nın
   "hile yapan kesilir (slash %30)" varsayımı **resmi olarak temelsizdir**.
3. **arXiv:2511.03434** (Kas 2025, AAAI 2026 workshop) — **Salt-reputation modelleri
   reputation-gaming'e kırılgandır**. Pactiva'da iki sahte kimlik birbirini onaylayabilir
   (`create_peer_attestation` sadece self-endorsement'i engeller, `worker_id != endorser_id`).
   `verified_peer_badge` (≥2 atıf) böylece kolayca sahtelenir.

**Doğrulanamadı (uydurulmadı):** "Schelling-tahkimi" ve "decentralized arbitration"
için **akademik referans bulunamadı** (`Schelling AND blockchain` → 0 sonuç;
`"decentralized arbitration"` → yalnızca ilgisiz 1 NFT makalesi). Yani projenin en
merkezi teriminin **doğrulanabilir akademik bir dayanağı yok**.

## 5. Neden (C)?

### Önce itiraf: iyi yanlar (objektif)
- **Kod kalitesi yüksek**: gerçek SQLite + FK emniyeti, Decimal ile parasal hesap,
  HMAC imzalı atıflar, quadratic-voting mantığı doğru implemente edilmiş, FastAPI +
  güvenlik başlıkları + rate-limiter + ptp_clock + offline_sync gibi **olumlu mühendislik
  disiplini** var.
- **Test disiplini güçlü**: 104 test, hepsi yeşil, gerçek yaşam-döngüsü senaryoları.
- **Çözmeye çalıştığı problem gerçek**: gig-pazarda aracı sömürüsü ve adverse selection.

### Ama temel değer iddiası çürüyor
Pactiva'yı "sıradan bir gig platformu"ndan ayıran **tek şey dağıtık-güvenilir emanet ve
tahkim**. Üç temel direği de literatür tarafından çürütülmüş:

| Pactiva'nın iddiası | Durum | Kanıt |
|---|---|---|
| Karesel oylama adil dağıtım sağlar | **Kırılır** — Sybil cüzdan-bölme ile | [1] imkânsızlık teoremi |
| Slashing hileyi caydırır/garantiler | **Garanti etmez** — risk-free saldırı dengesi var | [2] |
| Meslektaş itibarı güvenilir kanıt | **Oyunlanabilir** — karşılıklı sahte onay | [3] |
| "Schelling-tahkimi" dezentralize adalet | **Akademik dayanağı bulunamadı** | 0 sonuç |
| Akıllı sözleşmeler emaneti korur | **Simülasyon** — gerçek zincirde değil (README itiraf ediyor) | README |

### Hendeği (moat) kaldırınca ne kalıyor?
Güven-iddialarını çıkarınca Pactiva, **SQLite + FastAPI ile yazılmış bir gig-platform
CRUD uygulaması** olur: ilan, eşleştirme, escrow kayıtları, sözleşme PDF/HTML, QR,
ERP/THP mahsup fişi. Bunlar **gerçek ama teknik olarak standart** özelliklerdir.
Bir hendeğe değil, **satış/hukuk/operasyon** execution'ına ihtiyaç duyar — ki bu,
kod yazarak çözülebilecek bir şey değil. Ayrıca **Proje 22 + Proje 37'nin birleşimi**
olduğu için kapsam dağınık: 21 modül (qr_engine, vector_engine, erp_export, ptp_clock,
dispatch, liveness, offline_sync...) — hiçbiri "tek bir şeyi mükemmel yapan" değil.

### Niçin (B) değil?
(B) "olduğu gibi kalsın" dersek, arkasında **zaman/çaba yatırımı** gerektiren bir umut
bırakırız. Ama burada **ek mühendislik temel sorunu çözmez**: Sybil direnci için
kimlik-benzersizliği (biyometrik/devlet kimliği bağlama), slashing için dış yaptırım,
itibar için graph-based Sybil direnci gerekir — hepsi **başka bir ürün** demektir.
**Mevcut haliyle değeri "çalışan bir kod örneği"dir, savunulabilir bir ürün değildir.**

→ **Sonuç: (C) Rafa kaldır.** Kod silinmemeli (test hala yeşil, referans değerli),
ama **aktif geliştirme için zaman ayrılmamalı**.

---

## 6. Rafa kaldırma planı (düşük maliyetli)

1. **Kod olduğu gibi bırakılır** — testler hala 104/104 yeşil; bir şey bozulmaz.
2. `__pycache__/`, `.coverage`, `pactiva.db` **commit'ten çıkarılıp** `.gitignore` eklenir
   (sadece hijyen; 5 dakika).
3. README'ye **dürüst durum notu** eklenir: "Çekirdek güven-iddiaları 2026 literatürüyle
   çelişmektedir; bu repo referans/arşiv amaçlıdır." — ki kimse zamanını buraya yatırmasın.
4. **Aktif geliştirme yapılmaz**, demo/üretim dağıtımı yapılmaz.
5. Eğer ileride "Pactiva" fikri geri gelirse: **baştan**, kimlik-benzersizliği ve dış
   yaptırım üzerine kurulmuş **yeni bir mimariyle** gelinmeli — bu kod tabanı
   **yeniden kullanılabilir bileşen kütüphanesi** (QR, ERP mahsup, Decimal escrow) olarak
   faydalı olabilir.

## 7. Sonuç
**PACTIVA → (C).** Mühendislik iyi, **fikir bu gerçekleşmede ayakta kalamıyor**.
Zaman, Fleksa gibi **gerçek bir teknik hendeği ve literatür desteği olan** projeye
harcanmalı.
