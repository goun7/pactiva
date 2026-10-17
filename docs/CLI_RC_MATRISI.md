# Pactiva CLI RC-Matrisi ( Ölçülmüş Çıkış-Kodu Tablosu)

**Tarih:** 2026-10-18 · **DALGA-D2** · **Ölçüm-yöntemi:** `PACTIVA_DB_PATH=/tmp/... python3 -m pactiva_core.cli <cmd> ... > /tmp/x.txt 2>&1; echo RC=$?` ( PIPED-DEĞİL, gerçek-exit-code)

**Kabul-ölçütü ( argparse stdlib sözleşmesi):**
- `rc=0` → komut başarılı
- `rc=2` → GEÇERSİZ-GİRDİ / kullanım-hatası ( `parser.error()` — usage + stderr, traceback YOK)
- `rc=1` → çalışma-zamanı hatası ( traceback) — **geçersiz girdi için asla olmamalı**

## Matris ( komut × girdi × beklenen × ölçülen)

### Global / komut-seçimi

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| G1 | `--help` | 0 | **0** | ✓ | 8 komut listelenir |
| G2 | `lock-budget --help` | 0 | **0** | ✓ | Alt-komut kullanımı basılır |
| G3 | `bogus-command` | 2 | **2** | ✓ | `invalid choice: 'bogus-command'` |
| G4 | ( argsiz) | 2 | **2** | ✓ | `the following arguments are required: subcommand` |

### status

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| S1 | `status` | 0 | **0** | ✓ | İlan/aktif sayıları basılır |

### lock-budget

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| LB1 | `--title "T" --rate 300 --hours 8` | 0 | **0** | ✓ | `2880.00 TL` kilit |
| LB2 | `--rate abc` | 2 | **2** | ✓ | `invalid float value: 'abc'` |
| LB3 | `--hours abc` | 2 | **2** | ✓ | Aynı — type-scheması doğru |
| LB4 | ( `--title` YOK) | 2 | **2** | ✓ | `required: --title` |
| LB5 | `--category bogus` | 2 | **2** | ✓ | choices-reddi |
| LB6 | `--title ""` | 0 | **0** | ✓-ama-notlu | Boş-başlık içerik-dogrulamasız-kabul — zayıf-dogrulama ( rafta) |
| LB-N1 | `--rate -5` | 2 | **2** | ✓ ( D2-kapatma) | `❌ GEÇERSİZ GİRDİ: --rate pozitif olmalı` — stderr, traceback YOK |
| LB-N2 | `--hours -5` | 2 | **2** | ✓ ( D2-kapatma) | `❌ GEÇERSİZ GİRDİ: --hours pozitif olmalı` — stderr |

### release-escrow

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| RE1 | ( geçerli job-id lifecycle) | 0 | **0** | ✓ | lock-budget → release-escrow rc=0 |
| RE2 | `--payout abc` | 2 | **2** | ✓ | `invalid float value: 'abc'` |
| RE-N1 | var-olmayan `--job-id` | 2 | **2** | ✓ ( D2-kapatma) | `❌ GEÇERSİZ GİRDİ: <id> için emanet kasası hesabı bulunamadı.` — stderr, traceback YOK |

### generate-qr

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| QR1 | `generate-qr` | 0 | **0** | ✓ | `PACTIVA:...` token |

### dispatch

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| D1 | `dispatch` | 0 | **0** | ✓ | `DISPATCH_OFFERED`, arrival<10dk |
| D2 | `--rate abc` | 2 | **2** | ✓ | `invalid float value: 'abc'` |

### contract

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| C1 | `contract --title T --rate 400 --hours 10` | 0 | **0** | ✓ | SHA-256 hash + SGK/GVK onayları |
| C2 | `--hours abc` | 2 | **2** | ✓ | |
| C3 | `--rate abc` | 2 | **2** | ✓ | |

### audit-verify

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| A1 | `audit-verify` | 0 | **0** | ✓ | `KUSURSUZ (100% DOĞRULANDI)` |

### erp-export

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| E1 | `--format json` | 0 | **0** | ✓ | Boş-fatura → `[]` |
| E2 | `--format logo_xml` | 0 | **0** | ✓ | `<TRANSACTIONS>` |
| E3 | `--format sap_csv` | 0 | **0** | ✓ | CSV-başlığı ( boş-fatura) |
| E4 | `--format xml` | 2 | **2** | ✓ | `invalid choice: 'xml'` |

**Toplam: 29 satır.** Geçersiz-girdilerden hepsi rc=2 ( doğru) — 3 KIRMIZI-pin DALGA-D2-kapatma'da düzeltildi. Geri-kalan geçerli-yollar rc=0.

## Kırmızı-Pinlerin-Kapanması ( D2-kapatma, 2026-10-17)

Üç KIRMIZI-pin de **CLI katmanında** girdi-doğrulama eklenerek kapatıldı ( üretim-logic'ine — `math_models.py`, `repository.py` — DOKUNULMADI):

| Pin | Komut | Önce | Sonra | Düzeltme |
|-----|-------|------|-------|----------|
| `test_red_pin_lock_budget_negative_rate_must_be_rc2` | `lock-budget --rate -5` | rc=1 + `ValueError` | **rc=2** | `cmd_lock_budget`'e `rate <= 0` → stderr + `return 2` |
| `test_red_pin_lock_budget_negative_hours_must_be_rc2` | `lock-budget --hours -5` | rc=1 + `ValueError` | **rc=2** | Aynı — `hours <= 0` kontrolü |
| `test_red_pin_release_escrow_missing_job_must_be_rc2` | `release-escrow --job-id <yok>` | rc=1 + `ValueError` | **rc=2** | `cmd_release_escrow` önce `repo.get_escrow_by_job_id()` ile varlık-kontrolü → stderr + `return 2` |

**Dispatch-değişikliği:** `main()` artık `args.func(args)`'in dönüş-değerini `return rc or 0` ile döndürür; `sys.exit(main())` sadece `__main__` bloğunda. Bu sayede (1) `python3 -m pactiva_core.cli` alt-süreci gerçek rc'yi verir, (2) in-process `main()` çağrısı ( `tests/test_cli.py`) `SystemExit` fırlatmaz.

## Modül-Import Yan-Etkisi ( api.py:96)

`pactiva_core/api.py` modül-seviyesinde `init_db()` çağırır ( satır 96). `DEFAULT_DB_PATH = os.environ.get("PACTIVA_DB_PATH", "pactiva.db")` — **göreli**:

- **PACTIVA_DB_PATH set-iken:** import tmp'ye-yönelen DB'ye yazar — CWD'ye `pactiva.db` OLUŞMAZ ( pin-testi `test_pin_api_import_does_not_write_cwd_db` ile kanıtlandı — yeşil).
- **PACTIVA_DB_PATH set-DEĞİLKEN:** import CWD'ye `pactiva.db` yazar ( pin-testi `test_pin_api_import_without_env_leaks_to_cwd` ile kanıtlandı — yan-etki var).
- `tests/conftest.py` env'i subprocess'lere-miras-verdiği için **tüm suite CWD'den-bağımsız** çalışır. Mevcut-suite'teki izolasyon-kanıtı: bu-documanın-sonundaki suite-sonucu.

## Pin-Testleri

`tests/test_cli_rc_dallar.py` — **29 pin-testi: 29 YEŞİL** ( 3 KIRMIZI-pin D2-kapatma'da kapatıldı). Test-yöntemi: gerçek-subprocess ( `capture_output=True` — true-exit-code maskelenmez).

## Tam-Suite Sonucu ( pin'lerle)

```
timeout 600 python3 -m pytest -o addopts= -p no:cacheprovider -q > /tmp/pac_d2.txt 2>&1; echo RC=$?
```

Sonuç ( D2-kapatma sonrası): **226 passed rc=0** ( 3 kırmızı-pin yeşile-döndü). Önceki temel-suite **197 passed rc=0** iken pin-eklenmesiyle **223 passed**'a çıktı ( +26 yeşil-pin), D2-kapatma ile **226**'ya-çıktı.

**Suite-sonrası repo-root durumu:** `pactiva.db` / `*.sqlite*` OLUŞMADI — **TEMIZ** ( conftest-izolasyonu çalışıyor, kanıtlandı).

**Not ( ilk-ölçüm-tuzağı):** pin-testlerinin-ilk-taslağında `env` manuel-kurulduğunda conftest'in `PACTIVA_DB_PATH`'ini silmesi suite-sırasında CWD'ye `pactiva.db` ( 159.744 B) yazdırdı. Düzeltme: subprocess env'i `os.environ` üzerinden-türetilir ( conftest-değeri-miras-alır) — `test_pin_api_import_does_not_write_cwd_db` yeşil ve **suite-sonrası repo-root TEMIZ**.
