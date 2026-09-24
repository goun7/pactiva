# 🧩 ESLESTIRME_CORE — Paylaşılan Eşleştirme Çekirdeği Sözleşmesi (K4)

> **Nedir:** 22ve37 platformunun iki dikeyinin (Dikey-22 İş&İşçi / Dikey-37 Kariyer) birlikte kullandığı
> ortak eşleştirme çekirdeğinin dil-bağımsız sözleşmesi. K4 birleşmesinin ürettiği asıl artefakt budur:
> yeni bir "işgücü eşleştirme" fikri (ör. mavi/beyaz yaka dışı bir dikey) bu çekirdeğe adaptör yazar,
> iskeleti tekrar yazmaz.
> **Tarih:** 2026-09-04 · **Üst:** `Fikir.md` (22+37 kanonik) · `CERCEVE_OTONOM_AVCI_OPERATOR.md` §3

---

## 1. Girdi Modeli

### Aday vektörü (`Aday`)
| Alan | Dikey 22 kaynağı | Dikey 37 kaynağı |
|---|---|---|
| `vetkinlikler[]` | Fiziksel görevler, sertifikalar, deneyim | Bilişsel mikro-simülasyon sonuçları, eğitim |
| `kisitlar{}` | Çalışma saatleri, coğrafya, mobilite | Lokasyon/karma çalışma, maaş bandı |
| `guven{}` | Çapraz referans skoru, geofence geçmişi | Blind-profiling paketi (anonim), psikometrik tutarlılık |
| `kimlikRef` | Biyometrik canlılık token'ı (KVKK) | KVKK anonim anahtarı |

### Fırsat vektörü (`Firsat`)
| Alan | Dikey 22 | Dikey 37 |
|---|---|---|
| `gorev[]` | Fiziksel iş kalemleri + mesai şablonu | Rol gerekleri, proje kapsamı |
| `uygunluk` | İşveren bütçesi (escrow kilitli) | Gerçek ilan doğrulaması (ghost-job süzgeci geçmiş) |
| `odeme` | Saat/parça ücret + kesinti kuralı | Proje bütçesi + hak ediş takvimi |

## 2. Skor Fonksiyonu (tek, iki besleyici)

```
eslesme_skoru = w1·uygunluk(aday, firsat) + w2·guven(aday) − w3·hukuk_cezasi(...)
```

- `uygunluk(·)`: vektör benzerliği (alan ağırlıkları dikey konfigürasyonundan gelir).
- `guven(·)`: çapraz referans + canlılık/geofence veya psikometrik tutarlılık — **dikey başına seçilir**.
- `hukuk_cezasi(·)`: asgari ücret altı teklif, AB AI Act kapsam dışı kullanım, ayrımcılık filtresi → skoru sıfırlar.
- Eşik ve Kelly benzeri boyutlandırma `CERCEVE`'nin kasa katmanı kurallarına bağlıdır (Tier 1→5).

## 3. Ortak 8 Adım (Y1–Y8) — dikey harflerinin (J/C) üst kümesi

| Adım | Ortak iş | Dikey 22 (J) | Dikey 37 (C) |
|---|---|---|---|
| Y1 | Fırsat/talep tarama | İlan açma + bütçe kilitleme (J1) | Gerçek ilan tarama, hayalet süzgeç (C3) |
| Y2 | Aday profil alımı | Çapraz referans + itibar (J2) | Bilişsel mikro-simülasyon (C1) |
| Y3 | Doğrulama | Biyometrik canlılık + geofence (J3) | Psikometrik çapraz kontrol (C2) |
| Y4 | Hukuk/kimlik filtresi | Mesai/asgari ücret kontrolü (J4) | AB AI Act mühürleme (C4) |
| Y5 | Sinyal & IPC | IPC veri yolu (J5) | IPC veri yolu (C5) |
| Y6 | Teslim | Otomatik mesai + iş tamamlama (J4b) | 90 gün mikro-proje eşleme (C6) |
| Y7 | Tahsilat/sweep | Otonom jüri + makbuz + sweep (J6–J7) | B2B/B2C tahsilat sweep (C7) |
| Y8 | Sahtekârlık + kasa | Sahtekârlık önleme + kasa aktarımı (J8) | Aynı (C8) |

> Not: harf setleri (J1–J8 / C1–C8) kök fikirlerde korunur; Y1–Y8 bu çekirdeğin **ortak** harf setidir.

## 4. Çıktı Sözleşmesi (makine-okur)

```json
{
  "eslesmeId": "uuid",
  "dikey": "22 | 37",
  "adayRef": "hash",
  "firsatRef": "hash",
  "skor": 0.87,
  "bilesenler": { "uygunluk": 0.9, "guven": 0.82, "hukukCezasi": 0 },
  "adim": "Y6",
  "odemeKurali": { "tip": "escrow | mikro_proje", "miktar": 12500, "kesinti": "…" },
  "kanitPaketi": ["file://…/checkin_foto.jpg", "file://…/rapor.docx"],
  "ipcSinyali": { "mesh": "sovereign_signal_mesh", "kanal": "istihdam" }
}
```

## 5. Kullanım Kuralı

- Bu klasöre **yeni dikey** (ör. dikey temizlik, teslimat, freelance) ekleneceğinde: yeni `Dikey` konfigürasyonu
  `Fikir.md` §3 tablosuna bir satır + Adım-2/Adım-6 varyantı yazar, çekirdeğe dokunmaz.
- Çekirdek kodlandığında bu sözleşme SSOT'tur; kod `sözleşme v1.0` sürümüne uyar.
- Gerçek dünya referans uygulaması: masaüstü **HCS** dikeyi (ev temizliği) — bkz. `Fikir.md` §5.
